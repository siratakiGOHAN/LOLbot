import asyncio

import discord
from discord import app_commands

import core
import data_collector
import image_builder
import script

VALID_LANES = {"top", "jungle", "mid", "adc", "support"}


async def _run_update_task(
    riot_key: str,
    db_path: str,
    channel: discord.abc.Messageable,
) -> None:
    """バックグラウンドでデータ収集を実行し、完了・失敗をチャンネルに通知する。"""
    try:
        await data_collector.collect_high_elo_data(riot_key, db_path)
        await data_collector.sync_champion_names(db_path)
        await channel.send(script.MSG_UPDATE_DONE)
    except Exception as e:
        await channel.send(script.MSG_UPDATE_ERROR.format(error=e))


async def champion_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    """チャンピオン名のオートコンプリート候補を返す（最大25件）。"""
    if core._champion_cache is None:
        return []

    norm = current.lower().replace(" ", "").replace("・", "").replace("'", "").replace(".", "")

    exact: list[app_commands.Choice[str]] = []
    partial: list[app_commands.Choice[str]] = []

    for champ in core._champion_cache.values():
        name_ja = champ.get("name_ja", "")
        name_en = champ.get("name_en", "")
        norm_ja = name_ja.lower().replace("・", "").replace(" ", "")
        norm_en = name_en.lower().replace(" ", "").replace("'", "")
        display = f"{name_ja}（{name_en}）" if name_ja != name_en else name_en

        choice = app_commands.Choice(name=display[:100], value=name_en)

        if norm_ja == norm or norm_en == norm:
            exact.append(choice)
        elif norm and (norm in norm_ja or norm in norm_en):
            partial.append(choice)

        if len(exact) + len(partial) >= 25:
            break

    return (exact + partial)[:25]


def setup_commands(tree: app_commands.CommandTree, db_path: str, riot_key: str) -> None:
    @tree.command(name="lol", description="LoL マッチアップの統計データを表示します")
    @app_commands.describe(
        champion="対面チャンピオン名（日本語・英語どちらでも可）",
        lane="レーン（top / jungle / mid / adc / support）省略時は自動判定",
    )
    @app_commands.autocomplete(champion=champion_autocomplete)
    async def lol_command(
        interaction: discord.Interaction,
        champion: str,
        lane: str | None = None,
    ) -> None:
        await interaction.response.defer()

        resolved = core.resolve_champion(champion)
        if resolved is None:
            await interaction.followup.send(
                embed=build_error_embed(script.MSG_CHAMP_NOT_FOUND.format(name=champion))
            )
            return

        enemy_id, enemy_en, enemy_ja = resolved

        if lane is not None:
            lane_norm = lane.lower()
            if lane_norm not in VALID_LANES:
                await interaction.followup.send(
                    embed=build_error_embed(script.MSG_LANE_NOT_FOUND.format(lane=lane))
                )
                return
        else:
            lane_norm = await core.detect_main_lane(db_path, enemy_id)
            if lane_norm is None:
                lane_norm = "top"

        counters = await core.get_counters(db_path, enemy_id, lane_norm)
        if not counters:
            await interaction.followup.send(
                embed=build_error_embed(script.MSG_NO_DATA)
            )
            return

        embed = await build_counter_embed(db_path, enemy_id, enemy_en, enemy_ja, lane_norm, counters)
        view = CounterDetailView(db_path, counters, enemy_id, enemy_en, lane_norm)
        await interaction.followup.send(embed=embed, view=view)

    @tree.command(name="lolupdate", description="【管理者】マッチアップデータをRiot APIから再収集します（画像キャッシュは保持）")
    async def lolupdate_command(interaction: discord.Interaction) -> None:
        if not interaction.user.guild_permissions.administrator:  # type: ignore[union-attr]
            await interaction.response.send_message(script.MSG_NO_PERMISSION, ephemeral=True)
            return

        await interaction.response.send_message(script.MSG_UPDATE_STARTED)
        asyncio.create_task(_run_update_task(riot_key, db_path, interaction.channel))

    @tree.command(name="lolpatch", description="【管理者】パッチ適用後に実行。画像キャッシュとData Dragonキャッシュをリセットします")
    async def lolpatch_command(interaction: discord.Interaction) -> None:
        if not interaction.user.guild_permissions.administrator:  # type: ignore[union-attr]
            await interaction.response.send_message(script.MSG_NO_PERMISSION, ephemeral=True)
            return

        await interaction.response.defer()
        try:
            image_builder.clear_image_cache()
            await core.load_champion_cache(force=True)
            await core.load_item_cache(force=True)
            await core.load_rune_cache(force=True)
            await interaction.followup.send(script.MSG_PATCH_DONE)
        except Exception as e:
            await interaction.followup.send(script.MSG_PATCH_ERROR.format(error=e))


async def build_counter_embed(
    db_path: str,
    enemy_id: int,
    enemy_en: str,
    enemy_ja: str,
    lane: str,
    counters: list[dict],
) -> discord.Embed:
    lane_label = script.lane_display(lane)
    enemy_label = f"{enemy_ja}（{enemy_en}）" if enemy_ja != enemy_en else enemy_en

    embed = discord.Embed(
        title=script.MSG_TITLE.format(enemy=enemy_label, lane=lane_label),
        description=script.MSG_DESCRIPTION.format(count=len(counters)),
        color=discord.Color.gold(),
    )
    embed.set_thumbnail(url=core.cdimage_champion(enemy_id))

    for rank, counter in enumerate(counters, start=1):
        field_name, field_value = script.format_stats_field(counter, rank)

        # ビルドをテキストで表示（リンクなし）
        build = await core.get_build(db_path, counter["champion_id"], enemy_id, lane)
        if build and build["item_ids"]:
            item_names = " / ".join(core.resolve_item_name(i) for i in build["item_ids"])
            field_value += f"\n{script.MSG_BUILD_TITLE}: {item_names}"

        embed.add_field(name=field_name, value=field_value, inline=False)

    embed.set_footer(text="データはMaster以上のランク戦統計に基づきます。最終的な判断はプレイヤー自身が行うものです。")
    return embed


def build_error_embed(message: str) -> discord.Embed:
    return discord.Embed(
        title="エラー",
        description=message,
        color=discord.Color.red(),
    )


class CounterDetailView(discord.ui.View):
    """カウンター各チャンピオンのビルド画像を表示するボタン群。"""

    def __init__(
        self,
        db_path: str,
        counters: list[dict],
        enemy_id: int,
        enemy_en: str,
        lane: str,
    ) -> None:
        super().__init__(timeout=180)
        for i, counter in enumerate(counters):
            self.add_item(BuildButton(i, counter, db_path, enemy_id, enemy_en, lane))


class BuildButton(discord.ui.Button):
    def __init__(
        self,
        index: int,
        counter: dict,
        db_path: str,
        enemy_id: int,
        enemy_en: str,
        lane: str,
    ) -> None:
        name = counter.get("name_ja") or counter.get("name_en", "?")
        super().__init__(
            label=f"{index + 1}. {name}",
            style=discord.ButtonStyle.secondary,
            row=0,
        )
        self.counter = counter
        self.db_path = db_path
        self.enemy_id = enemy_id
        self.enemy_en = enemy_en
        self.lane = lane

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        builds = await core.get_builds(self.db_path, self.counter["champion_id"], self.enemy_id, self.lane)
        if not builds:
            await interaction.followup.send(script.MSG_NO_DATA, ephemeral=True)
            return

        name_ja = self.counter.get("name_ja") or self.counter.get("name_en", "")
        name_en = self.counter.get("name_en", "")
        lane_label = script.lane_display(self.lane)
        yt_url = script.youtube_url(name_en, self.enemy_en, lane_label)

        embed = discord.Embed(
            title=f"{name_ja}（{name_en}） のビルドデータ",
            color=discord.Color.blue(),
        )
        embed.set_thumbnail(url=core.cdimage_champion(self.counter["champion_id"]))

        for i, build in enumerate(builds, start=1):
            item_names = " / ".join(core.resolve_item_name(x) for x in build["item_ids"])
            keystone_id = str(build["keystone_id"]) if build.get("keystone_id") else None
            rune_name = core.resolve_rune_name(keystone_id) if keystone_id else None
            win_pct = build["wins"] / build["games"] * 100 if build["games"] else 0

            lines = [f"**アイテム:** {item_names}"]
            if rune_name:
                lines.append(f"**キーストーン:** {rune_name}")
            lines.append(f"勝率: {win_pct:.1f}% ({build['games']}試合)")

            embed.add_field(
                name=f"パターン {i}",
                value="\n".join(lines),
                inline=False,
            )

        embed.add_field(
            name=script.MSG_YOUTUBE_LABEL,
            value=f"[動画を見る]({yt_url})",
            inline=False,
        )

        build_rows = []
        for b in builds:
            ks_id = str(b["keystone_id"]) if b.get("keystone_id") else None
            build_rows.append({
                "item_ids": b["item_ids"],
                "icon_url_map": {str(item_id): core.ddragon_item_image(item_id) for item_id in b["item_ids"]},
                "keystone_id": ks_id,
                "keystone_url": core.ddragon_rune_image(ks_id) if ks_id else None,
            })

        img_path = await image_builder.get_builds_image(build_rows)

        if img_path:
            file = discord.File(str(img_path), filename="build.png")
            embed.set_image(url="attachment://build.png")
            await interaction.followup.send(file=file, embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(embed=embed, ephemeral=True)
