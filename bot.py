import os
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

from database import (
    setup_database,
    register_player,
    get_player,
    get_all_active_players,
    create_challenge,
    get_challenge,
    get_pending_challenges_for_player,
    accept_challenge,
    decline_challenge,
    lock_points_for_challenge,
    submit_winner_report,
    check_match_reports,
    mark_challenge_disputed,
    complete_challenge_and_transfer_points,
    resolve_dispute_and_transfer_points,
    admin_adjust_points,
    admin_add_or_restore_player,
    admin_set_player_status,
    expire_old_pending_challenges,
    apply_inactivity_penalties,
    create_rule_proposal,
    get_rule_proposal,
    approve_rule_as_admin,
    approve_rule_as_player,
    reject_rule_as_player,
    get_rule_counts,
    approve_rule_if_ready,
    fail_rule_proposal,
)

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
ADMIN_ROLE_NAME = "Admin"

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)


def has_admin_role(member: discord.Member):
    return any(role.name == ADMIN_ROLE_NAME for role in member.roles)


def rule_ping(interaction: discord.Interaction):
    admin_role = discord.utils.get(interaction.guild.roles, name=ADMIN_ROLE_NAME)
    admin_ping = admin_role.mention if admin_role else "@Admin"
    return f"@everyone {admin_ping}"


def format_points(player_data):
    discord_id, username, total_points, locked_points, status, inactive_streak, last_point_change, last_inactivity_penalty = player_data
    available_points = total_points - locked_points

    return (
        f"**{username}**\n"
        f"Status: **{status}**\n"
        f"Total Points: **{total_points}**\n"
        f"Available Points: **{available_points}**\n"
        f"Locked Points: **{locked_points}**\n"
        f"Inactive Streak: **{inactive_streak}**"
    )


@bot.event
async def on_ready():
    setup_database()
    print(f"{bot.user} is online and ready.")

    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash command(s).")
    except Exception as e:
        print(f"Slash command sync failed: {e}")

    if not maintenance_loop.is_running():
        maintenance_loop.start()


@tasks.loop(hours=1)
async def maintenance_loop():
    expired = expire_old_pending_challenges()
    penalties = apply_inactivity_penalties()

    if expired:
        print(f"Expired {expired} old pending challenge(s).")

    for username, penalty, new_points, new_status in penalties:
        print(f"Inactivity penalty: {username} lost {penalty}. New points: {new_points}. Status: {new_status}")


@bot.tree.command(name="ping", description="Check if the bot is online.")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("Culling Game Master is online.")


@bot.tree.command(name="register", description="Register yourself as a player in The Culling Games.")
async def register(interaction: discord.Interaction):
    user = interaction.user

    if get_player(user.id):
        await interaction.response.send_message(f"{user.mention}, you are already registered.", ephemeral=True)
        return

    register_player(user.id, user.display_name)
    await interaction.response.send_message(f"{user.mention} has entered **The Culling Games** with **100 points**.")


@bot.tree.command(name="points", description="Check your points or another player's points.")
async def points(interaction: discord.Interaction, player: discord.Member = None):
    target = player or interaction.user
    player_data = get_player(target.id)

    if not player_data:
        await interaction.response.send_message(f"{target.mention} is not registered.", ephemeral=True)
        return

    await interaction.response.send_message(format_points(player_data))


@bot.tree.command(name="leaderboard", description="Show the public Culling Games leaderboard.")
async def leaderboard(interaction: discord.Interaction):
    players = get_all_active_players()

    if not players:
        await interaction.response.send_message("No active players are registered yet.")
        return

    text = "**The Culling Games Leaderboard**\n\n"

    for index, player_data in enumerate(players, start=1):
        username, points, locked_points, status = player_data
        available = points - locked_points
        text += f"**{index}. {username}** — {points} total ({available} available, {locked_points} locked)\n"

    await interaction.response.send_message(text)


@bot.tree.command(name="challenge", description="Challenge another player for an exact point wager.")
async def challenge(interaction: discord.Interaction, opponent: discord.Member, game: str, wager: int):
    challenger = interaction.user

    if opponent.bot:
        await interaction.response.send_message("You cannot challenge a bot.", ephemeral=True)
        return

    if opponent.id == challenger.id:
        await interaction.response.send_message("You cannot challenge yourself.", ephemeral=True)
        return

    if wager <= 0:
        await interaction.response.send_message("The wager must be an exact number greater than 0.", ephemeral=True)
        return

    challenger_data = get_player(challenger.id)
    opponent_data = get_player(opponent.id)

    if not challenger_data:
        await interaction.response.send_message("You must register first.", ephemeral=True)
        return

    if not opponent_data:
        await interaction.response.send_message(f"{opponent.mention} is not registered.", ephemeral=True)
        return

    _, _, challenger_points, challenger_locked, challenger_status, _, _, _ = challenger_data
    _, _, opponent_points, opponent_locked, opponent_status, _, _, _ = opponent_data

    if challenger_status != "active":
        await interaction.response.send_message("You are not an active player.", ephemeral=True)
        return

    if opponent_status != "active":
        await interaction.response.send_message(f"{opponent.mention} is not an active player.", ephemeral=True)
        return

    challenger_available = challenger_points - challenger_locked
    opponent_available = opponent_points - opponent_locked

    if wager > challenger_available:
        await interaction.response.send_message(f"You only have **{challenger_available} available points**.", ephemeral=True)
        return

    if wager > opponent_available:
        await interaction.response.send_message(f"{opponent.mention} only has **{opponent_available} available points**.", ephemeral=True)
        return

    challenge_id = create_challenge(
        challenger.id,
        challenger.display_name,
        opponent.id,
        opponent.display_name,
        game,
        wager
    )

    await interaction.response.send_message(
        f"⚔️ **Challenge Created**\n\n"
        f"**Challenge ID:** {challenge_id}\n"
        f"**Challenger:** {challenger.mention}\n"
        f"**Opponent:** {opponent.mention}\n"
        f"**Game:** {game}\n"
        f"**Wager:** {wager} points\n\n"
        f"{opponent.mention}, use `/accept challenge_id:{challenge_id}` or `/decline challenge_id:{challenge_id}`.\n\n"
        f"This challenge expires after 7 days if not accepted or declined."
    )


@bot.tree.command(name="mychallenges", description="Show pending challenges sent to you.")
async def mychallenges(interaction: discord.Interaction):
    user = interaction.user

    if not get_player(user.id):
        await interaction.response.send_message("You are not registered.", ephemeral=True)
        return

    challenges = get_pending_challenges_for_player(user.id)

    if not challenges:
        await interaction.response.send_message("You have no pending challenges.", ephemeral=True)
        return

    text = "**Pending Challenges Sent To You**\n\n"

    for challenge_data in challenges:
        challenge_id, challenger_name, opponent_name, game, wager, status, created_at = challenge_data
        text += (
            f"**Challenge ID:** {challenge_id}\n"
            f"**From:** {challenger_name}\n"
            f"**Game:** {game}\n"
            f"**Wager:** {wager} points\n\n"
        )

    await interaction.response.send_message(text, ephemeral=True)


@bot.tree.command(name="accept", description="Accept a pending challenge.")
async def accept(interaction: discord.Interaction, challenge_id: int):
    user = interaction.user
    challenge_data = get_challenge(challenge_id)

    if not challenge_data:
        await interaction.response.send_message("That challenge does not exist.", ephemeral=True)
        return

    (
        cid, challenger_id, challenger_name, opponent_id, opponent_name,
        game, wager, status,
        challenger_reported_winner_id, challenger_reported_winner_name,
        opponent_reported_winner_id, opponent_reported_winner_name,
        created_at, accepted_at, completed_at
    ) = challenge_data

    if str(user.id) != str(opponent_id):
        await interaction.response.send_message("Only the challenged opponent can accept this challenge.", ephemeral=True)
        return

    if status != "pending":
        await interaction.response.send_message(f"This challenge is not pending. Current status: **{status}**.", ephemeral=True)
        return

    challenger_data = get_player(challenger_id)
    opponent_data = get_player(opponent_id)

    if not challenger_data or not opponent_data:
        await interaction.response.send_message("One of the players is no longer registered.", ephemeral=True)
        return

    _, _, challenger_points, challenger_locked, challenger_status, _, _, _ = challenger_data
    _, _, opponent_points, opponent_locked, opponent_status, _, _, _ = opponent_data

    if challenger_status != "active" or opponent_status != "active":
        await interaction.response.send_message("Both players must be active.", ephemeral=True)
        return

    if wager > challenger_points - challenger_locked:
        await interaction.response.send_message("The challenger no longer has enough available points.", ephemeral=True)
        return

    if wager > opponent_points - opponent_locked:
        await interaction.response.send_message("You no longer have enough available points.", ephemeral=True)
        return

    success = accept_challenge(challenge_id)

    if not success:
        await interaction.response.send_message("This challenge could not be accepted.", ephemeral=True)
        return

    lock_points_for_challenge(challenger_id, opponent_id, wager)

    await interaction.response.send_message(
        f"✅ **Challenge Accepted**\n\n"
        f"**Challenge ID:** {challenge_id}\n"
        f"**Game:** {game}\n"
        f"**Wager:** {wager} points\n"
        f"**Players:** <@{challenger_id}> vs <@{opponent_id}>\n\n"
        f"After the match, both players must use:\n"
        f"`/reportwinner challenge_id:{challenge_id} winner:@WinnerName`\n\n"
        f"Points only move if both players report the same winner."
    )


@bot.tree.command(name="decline", description="Decline a pending challenge.")
async def decline(interaction: discord.Interaction, challenge_id: int):
    user = interaction.user
    challenge_data = get_challenge(challenge_id)

    if not challenge_data:
        await interaction.response.send_message("That challenge does not exist.", ephemeral=True)
        return

    (
        cid, challenger_id, challenger_name, opponent_id, opponent_name,
        game, wager, status,
        challenger_reported_winner_id, challenger_reported_winner_name,
        opponent_reported_winner_id, opponent_reported_winner_name,
        created_at, accepted_at, completed_at
    ) = challenge_data

    if str(user.id) != str(opponent_id):
        await interaction.response.send_message("Only the challenged opponent can decline this challenge.", ephemeral=True)
        return

    if status != "pending":
        await interaction.response.send_message(f"This challenge is not pending. Current status: **{status}**.", ephemeral=True)
        return

    success = decline_challenge(challenge_id)

    if not success:
        await interaction.response.send_message("This challenge could not be declined.", ephemeral=True)
        return

    await interaction.response.send_message(
        f"❌ **Challenge Declined**\n\n"
        f"**Challenge ID:** {challenge_id}\n"
        f"**Opponent:** {user.mention}\n"
        f"**Game:** {game}\n"
        f"**Wager:** {wager} points"
    )


@bot.tree.command(name="reportwinner", description="Report the winner of an accepted challenge.")
async def reportwinner(interaction: discord.Interaction, challenge_id: int, winner: discord.Member):
    reporter = interaction.user
    challenge_data = get_challenge(challenge_id)

    if not challenge_data:
        await interaction.response.send_message("That challenge does not exist.", ephemeral=True)
        return

    (
        cid, challenger_id, challenger_name, opponent_id, opponent_name,
        game, wager, status,
        challenger_reported_winner_id, challenger_reported_winner_name,
        opponent_reported_winner_id, opponent_reported_winner_name,
        created_at, accepted_at, completed_at
    ) = challenge_data

    if status != "accepted":
        await interaction.response.send_message(f"This challenge is not accepting winner reports. Current status: **{status}**.", ephemeral=True)
        return

    if str(reporter.id) not in [str(challenger_id), str(opponent_id)]:
        await interaction.response.send_message("Only players in this challenge can report the winner.", ephemeral=True)
        return

    if str(winner.id) not in [str(challenger_id), str(opponent_id)]:
        await interaction.response.send_message("The winner must be one of the two players in this challenge.", ephemeral=True)
        return

    success, message = submit_winner_report(challenge_id, reporter.id, winner.id, winner.display_name)

    if not success:
        await interaction.response.send_message(message, ephemeral=True)
        return

    report_status, matched_winner_id = check_match_reports(challenge_id)

    if report_status == "waiting":
        await interaction.response.send_message(
            f"📝 **Winner Report Submitted**\n\n"
            f"**Challenge ID:** {challenge_id}\n"
            f"**Reported Winner:** {winner.mention}\n\n"
            f"Waiting for the other player to report the winner."
        )
        return

    if report_status == "matched":
        payout_success, result = complete_challenge_and_transfer_points(
            challenge_id,
            matched_winner_id,
            "Both players confirmed result"
        )

        if not payout_success:
            await interaction.response.send_message(f"Reports matched, but payout failed: {result}", ephemeral=True)
            return

        eliminated_text = ""
        if result["loser_status"] == "eliminated":
            eliminated_text = f"\n\n💀 **{result['loser_name']} has reached 0 points and is eliminated.**"

        await interaction.response.send_message(
            f"🏆 **Match Completed**\n\n"
            f"**Challenge ID:** {challenge_id}\n"
            f"**Game:** {result['game']}\n"
            f"**Wager:** {result['wager']} points\n\n"
            f"**Winner:** {result['winner_name']} → {result['winner_new_points']} points\n"
            f"**Loser:** {result['loser_name']} → {result['loser_new_points']} points"
            f"{eliminated_text}"
        )
        return

    if report_status == "disputed":
        mark_challenge_disputed(challenge_id)

        admin_role = discord.utils.get(interaction.guild.roles, name=ADMIN_ROLE_NAME)
        admin_ping = admin_role.mention if admin_role else "**Admin role not found**"

        await interaction.response.send_message(
            f"⚠️ **Match Disputed**\n\n"
            f"{admin_ping}\n\n"
            f"**Challenge ID:** {challenge_id}\n"
            f"**Game:** {game}\n"
            f"**Wager:** {wager} points\n"
            f"**Players:** <@{challenger_id}> vs <@{opponent_id}>\n\n"
            f"The players reported different winners. Points stay locked until an admin uses:\n"
            f"`/resolvedispute challenge_id:{challenge_id} winner:@Player reason:proof/reason`"
        )
        return

    await interaction.response.send_message("Something went wrong while checking reports.", ephemeral=True)


@bot.tree.command(name="resolvedispute", description="Admin command: resolve a disputed match.")
async def resolvedispute(interaction: discord.Interaction, challenge_id: int, winner: discord.Member, reason: str):
    if not has_admin_role(interaction.user):
        await interaction.response.send_message("Only Admins can use this command.", ephemeral=True)
        return

    success, result = resolve_dispute_and_transfer_points(
        challenge_id,
        winner.id,
        interaction.user.display_name,
        reason
    )

    if not success:
        await interaction.response.send_message(result, ephemeral=True)
        return

    eliminated_text = ""
    if result["loser_status"] == "eliminated":
        eliminated_text = f"\n\n💀 **{result['loser_name']} has reached 0 points and is eliminated.**"

    await interaction.response.send_message(
        f"🛠️ **Dispute Resolved by Admin**\n\n"
        f"**Challenge ID:** {challenge_id}\n"
        f"**Game:** {result['game']}\n"
        f"**Wager:** {result['wager']} points\n"
        f"**Reason:** {reason}\n\n"
        f"**Winner:** {result['winner_name']} → {result['winner_new_points']} points\n"
        f"**Loser:** {result['loser_name']} → {result['loser_new_points']} points"
        f"{eliminated_text}"
    )


@bot.tree.command(name="adminpoints", description="Admin command: add, remove, or set player points.")
async def adminpoints(interaction: discord.Interaction, player: discord.Member, action: str, amount: int, reason: str):
    if not has_admin_role(interaction.user):
        await interaction.response.send_message("Only Admins can use this command.", ephemeral=True)
        return

    action = action.lower()

    if action not in ["add", "remove", "set"]:
        await interaction.response.send_message("Action must be add, remove, or set.", ephemeral=True)
        return

    if amount < 0:
        await interaction.response.send_message("Amount cannot be negative.", ephemeral=True)
        return

    success, result = admin_adjust_points(
        player.id,
        player.display_name,
        action,
        amount,
        reason,
        interaction.user.display_name
    )

    if not success:
        await interaction.response.send_message(result, ephemeral=True)
        return

    await interaction.response.send_message(
        f"🛠️ **Admin Point Override**\n\n"
        f"**Player:** {player.mention}\n"
        f"**Action:** {action}\n"
        f"**Old Points:** {result['old_points']}\n"
        f"**New Points:** {result['new_points']}\n"
        f"**Status:** {result['status']}\n"
        f"**Reason:** {reason}"
    )


@bot.tree.command(name="adminplayer", description="Admin command: add, restore, remove, or eliminate a player.")
async def adminplayer(interaction: discord.Interaction, player: discord.Member, action: str, points: int, reason: str):
    if not has_admin_role(interaction.user):
        await interaction.response.send_message("Only Admins can use this command.", ephemeral=True)
        return

    action = action.lower()

    if action in ["add", "restore"]:
        admin_add_or_restore_player(
            player.id,
            player.display_name,
            points,
            reason,
            interaction.user.display_name
        )

        await interaction.response.send_message(
            f"🛠️ **Admin Player Update**\n\n"
            f"**Player:** {player.mention}\n"
            f"**Action:** {action}\n"
            f"**Points:** {points}\n"
            f"**Status:** active\n"
            f"**Reason:** {reason}"
        )
        return

    if action == "remove":
        success, message = admin_set_player_status(player.id, "removed", reason, interaction.user.display_name)
    elif action == "eliminate":
        success, message = admin_set_player_status(player.id, "eliminated", reason, interaction.user.display_name)
    else:
        await interaction.response.send_message("Action must be add, restore, remove, or eliminate.", ephemeral=True)
        return

    if not success:
        await interaction.response.send_message(message, ephemeral=True)
        return

    await interaction.response.send_message(
        f"🛠️ **Admin Player Update**\n\n"
        f"**Player:** {player.mention}\n"
        f"**Action:** {action}\n"
        f"**Reason:** {reason}"
    )


@bot.tree.command(name="proposerule", description="Spend 100 points to propose a rule change.")
async def proposerule(interaction: discord.Interaction, rule_text: str):
    user = interaction.user

    success, result = create_rule_proposal(user.id, user.display_name, rule_text)

    if not success:
        await interaction.response.send_message(result, ephemeral=True)
        return

    proposal_id = result
    ping_text = rule_ping(interaction)

    await interaction.response.send_message(
        f"{ping_text}\n\n"
        f"📜 **New Rule Proposal Created**\n\n"
        f"**Proposal ID:** {proposal_id}\n"
        f"**Proposed By:** {user.mention}\n"
        f"**Cost:** 100 points\n\n"
        f"**Proposed Rule:**\n{rule_text}\n\n"
        f"This rule passes only if it receives:\n"
        f"**1 Admin approval** and **3 active player approvals**.\n\n"
        f"Use `/approverule proposal_id:{proposal_id}` to vote yes.\n"
        f"Use `/rejectrule proposal_id:{proposal_id}` to vote no.\n\n"
        f"Rejection votes from players do not block the rule from passing.\n"
        f"An Admin no vote fails the rule."
    )


@bot.tree.command(name="approverule", description="Approve a pending rule proposal.")
async def approverule(interaction: discord.Interaction, proposal_id: int):
    user = interaction.user
    proposal = get_rule_proposal(proposal_id)

    if not proposal:
        await interaction.response.send_message("Rule proposal not found.", ephemeral=True)
        return

    (
        pid, proposer_id, proposer_name, rule_text, status,
        admin_approved, admin_approved_by, created_at, approved_at
    ) = proposal

    if status != "pending":
        await interaction.response.send_message(f"This proposal is not pending. Current status: **{status}**.", ephemeral=True)
        return

    if has_admin_role(user):
        admin_success = approve_rule_as_admin(proposal_id, user.display_name)

        if not admin_success:
            await interaction.response.send_message("Admin approval was already recorded or failed.", ephemeral=True)
            return

        vote_message = f"🛡️ **Admin Yes Vote Recorded**\n\n**Admin:** {user.mention}"
    else:
        player_success, player_message = approve_rule_as_player(proposal_id, user.id, user.display_name)

        if not player_success:
            await interaction.response.send_message(player_message, ephemeral=True)
            return

        vote_message = f"✅ **Player Yes Vote Recorded**\n\n**Player:** {user.mention}"

    approved_now = approve_rule_if_ready(proposal_id)
    counts = get_rule_counts(proposal_id)

    if not counts:
        await interaction.response.send_message("Could not check proposal counts.", ephemeral=True)
        return

    admin_count, player_yes_count, player_no_count = counts
    ping_text = rule_ping(interaction)

    if approved_now:
        await interaction.response.send_message(
            f"{ping_text}\n\n"
            f"✅ **Rule Proposal Passed**\n\n"
            f"**Proposal ID:** {proposal_id}\n"
            f"**Rule:**\n{rule_text}\n\n"
            f"**Admin Approval:** Yes\n"
            f"**Player Yes Votes:** {player_yes_count}/3\n"
            f"**No Votes:** {player_no_count}\n\n"
            f"The rule received the required approval and is now official."
        )
        return

    await interaction.response.send_message(
        f"{ping_text}\n\n"
        f"{vote_message}\n\n"
        f"**Proposal ID:** {proposal_id}\n"
        f"**Admin Approval:** {'Yes' if admin_count else 'No'}\n"
        f"**Player Yes Votes:** {player_yes_count}/3\n"
        f"**No Votes:** {player_no_count}\n\n"
        f"**Rule:**\n{rule_text}"
    )


@bot.tree.command(name="rejectrule", description="Vote no on a pending rule proposal.")
async def rejectrule(interaction: discord.Interaction, proposal_id: int):
    user = interaction.user
    proposal = get_rule_proposal(proposal_id)

    if not proposal:
        await interaction.response.send_message("Rule proposal not found.", ephemeral=True)
        return

    (
        pid, proposer_id, proposer_name, rule_text, status,
        admin_approved, admin_approved_by, created_at, approved_at
    ) = proposal

    if status != "pending":
        await interaction.response.send_message(
            f"This proposal is not pending. Current status: **{status}**.",
            ephemeral=True
        )
        return

    # Admin no vote = rule fails immediately and pings @everyone + @Admin
    if has_admin_role(user):
        fail_reason = "Admin voted no on the rule proposal."

        success, result = fail_rule_proposal(
            proposal_id,
            user.display_name,
            fail_reason
        )

        if not success:
            await interaction.response.send_message(result, ephemeral=True)
            return

        counts = get_rule_counts(proposal_id)

        if not counts:
            await interaction.response.send_message("Could not check proposal counts.", ephemeral=True)
            return

        admin_count, player_yes_count, player_no_count = counts
        ping_text = rule_ping(interaction)

        await interaction.response.send_message(
            f"{ping_text}\n\n"
            f"❌ **Rule Proposal Failed**\n\n"
            f"**Proposal ID:** {proposal_id}\n"
            f"**Failed By:** {user.mention}\n"
            f"**Reason:** Admin voted no.\n\n"
            f"**Admin Approval:** {'Yes' if admin_count else 'No'}\n"
            f"**Player Yes Votes:** {player_yes_count}/3\n"
            f"**No Votes:** {player_no_count}\n\n"
            f"**Rule:**\n{rule_text}"
        )
        return

    # Player no vote = no ping, does not fail the rule
    success, message = reject_rule_as_player(
        proposal_id,
        user.id,
        user.display_name
    )

    if not success:
        await interaction.response.send_message(message, ephemeral=True)
        return

    counts = get_rule_counts(proposal_id)

    if not counts:
        await interaction.response.send_message("Could not check proposal counts.", ephemeral=True)
        return

    admin_count, player_yes_count, player_no_count = counts

    await interaction.response.send_message(
        f"❌ **No Vote Recorded**\n\n"
        f"**Proposal ID:** {proposal_id}\n"
        f"**Voter:** {user.mention}\n"
        f"**Admin Approval:** {'Yes' if admin_count else 'No'}\n"
        f"**Player Yes Votes:** {player_yes_count}/3\n"
        f"**No Votes:** {player_no_count}\n\n"
        f"No votes from players do not block the rule from passing.\n"
        f"Only an Admin no vote fails the rule."
    )


@bot.tree.command(name="failrule", description="Admin command: fail a pending rule proposal.")
async def failrule(interaction: discord.Interaction, proposal_id: int, reason: str):
    if not has_admin_role(interaction.user):
        await interaction.response.send_message("Only Admins can use this command.", ephemeral=True)
        return

    proposal = get_rule_proposal(proposal_id)

    if not proposal:
        await interaction.response.send_message("Rule proposal not found.", ephemeral=True)
        return

    (
        pid, proposer_id, proposer_name, rule_text, status,
        admin_approved, admin_approved_by, created_at, approved_at
    ) = proposal

    if status != "pending":
        await interaction.response.send_message(f"This proposal is not pending. Current status: **{status}**.", ephemeral=True)
        return

    success, result = fail_rule_proposal(proposal_id, interaction.user.display_name, reason)

    if not success:
        await interaction.response.send_message(result, ephemeral=True)
        return

    counts = get_rule_counts(proposal_id)

    if not counts:
        await interaction.response.send_message("Could not check proposal counts.", ephemeral=True)
        return

    admin_count, player_yes_count, player_no_count = counts
    ping_text = rule_ping(interaction)

    await interaction.response.send_message(
        f"{ping_text}\n\n"
        f"❌ **Rule Proposal Failed**\n\n"
        f"**Proposal ID:** {proposal_id}\n"
        f"**Failed By:** {interaction.user.mention}\n"
        f"**Reason:** {reason}\n\n"
        f"**Admin Approval:** {'Yes' if admin_count else 'No'}\n"
        f"**Player Yes Votes:** {player_yes_count}/3\n"
        f"**No Votes:** {player_no_count}\n\n"
        f"**Rule:**\n{rule_text}"
    )


@bot.tree.command(name="rulestatus", description="Check a rule proposal's approval status.")
async def rulestatus(interaction: discord.Interaction, proposal_id: int):
    proposal = get_rule_proposal(proposal_id)

    if not proposal:
        await interaction.response.send_message("Rule proposal not found.", ephemeral=True)
        return

    (
        pid, proposer_id, proposer_name, rule_text, status,
        admin_approved, admin_approved_by, created_at, approved_at
    ) = proposal

    counts = get_rule_counts(proposal_id)

    if not counts:
        await interaction.response.send_message("Could not check proposal counts.", ephemeral=True)
        return

    admin_count, player_yes_count, player_no_count = counts

    await interaction.response.send_message(
        f"📜 **Rule Proposal Status**\n\n"
        f"**Proposal ID:** {proposal_id}\n"
        f"**Status:** {status}\n"
        f"**Proposed By:** {proposer_name}\n"
        f"**Admin Approval:** {'Yes' if admin_count else 'No'}\n"
        f"**Player Yes Votes:** {player_yes_count}/3\n"
        f"**No Votes:** {player_no_count}\n\n"
        f"**Rule:**\n{rule_text}"
    )


if TOKEN is None:
    print("ERROR: DISCORD_TOKEN was not found. Check your .env file.")
else:
    bot.run(TOKEN)