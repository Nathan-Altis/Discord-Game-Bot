import sqlite3
from datetime import datetime, timezone, timedelta

DB_NAME = "culling_games.db"


def get_connection():
    return sqlite3.connect(DB_NAME)


def get_now():
    return datetime.now(timezone.utc).isoformat()


def parse_time(value):
    if not value:
        return None
    return datetime.fromisoformat(value)


def setup_database():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS players (
            discord_id TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            points INTEGER NOT NULL DEFAULT 100,
            locked_points INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'active',
            inactive_streak INTEGER NOT NULL DEFAULT 0,
            last_point_change TEXT NOT NULL,
            last_inactivity_penalty TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS point_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            discord_id TEXT NOT NULL,
            username TEXT NOT NULL,
            old_points INTEGER NOT NULL,
            new_points INTEGER NOT NULL,
            change_amount INTEGER NOT NULL,
            reason TEXT NOT NULL,
            changed_by TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS challenges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            challenger_id TEXT NOT NULL,
            challenger_name TEXT NOT NULL,
            opponent_id TEXT NOT NULL,
            opponent_name TEXT NOT NULL,
            game TEXT NOT NULL,
            wager INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            challenger_reported_winner_id TEXT,
            challenger_reported_winner_name TEXT,
            opponent_reported_winner_id TEXT,
            opponent_reported_winner_name TEXT,
            created_at TEXT NOT NULL,
            accepted_at TEXT,
            completed_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rule_proposals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proposer_id TEXT NOT NULL,
            proposer_name TEXT NOT NULL,
            rule_text TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            admin_approved INTEGER NOT NULL DEFAULT 0,
            admin_approved_by TEXT,
            created_at TEXT NOT NULL,
            approved_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rule_approvals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proposal_id INTEGER NOT NULL,
            voter_id TEXT NOT NULL,
            voter_name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(proposal_id, voter_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rule_rejections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proposal_id INTEGER NOT NULL,
            voter_id TEXT NOT NULL,
            voter_name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(proposal_id, voter_id)
        )
    """)

    conn.commit()
    conn.close()


def log_point_change(cursor, discord_id, username, old_points, new_points, reason, changed_by):
    cursor.execute("""
        INSERT INTO point_history (
            discord_id, username, old_points, new_points,
            change_amount, reason, changed_by, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        str(discord_id),
        username,
        old_points,
        new_points,
        new_points - old_points,
        reason,
        changed_by,
        get_now()
    ))


def register_player(discord_id, username):
    conn = get_connection()
    cursor = conn.cursor()
    now = get_now()

    cursor.execute("""
        INSERT OR IGNORE INTO players (
            discord_id, username, points, locked_points, status,
            inactive_streak, last_point_change, last_inactivity_penalty
        )
        VALUES (?, ?, 100, 0, 'active', 0, ?, NULL)
    """, (str(discord_id), username, now))

    conn.commit()
    conn.close()


def get_player(discord_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT discord_id, username, points, locked_points, status,
               inactive_streak, last_point_change, last_inactivity_penalty
        FROM players
        WHERE discord_id = ?
    """, (str(discord_id),))

    player = cursor.fetchone()
    conn.close()
    return player


def get_all_active_players():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT username, points, locked_points, status
        FROM players
        WHERE status = 'active'
        ORDER BY points DESC
    """)

    players = cursor.fetchall()
    conn.close()
    return players


def create_challenge(challenger_id, challenger_name, opponent_id, opponent_name, game, wager):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO challenges (
            challenger_id, challenger_name, opponent_id, opponent_name,
            game, wager, status, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
    """, (
        str(challenger_id),
        challenger_name,
        str(opponent_id),
        opponent_name,
        game,
        wager,
        get_now()
    ))

    challenge_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return challenge_id


def get_challenge(challenge_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, challenger_id, challenger_name, opponent_id, opponent_name,
               game, wager, status,
               challenger_reported_winner_id, challenger_reported_winner_name,
               opponent_reported_winner_id, opponent_reported_winner_name,
               created_at, accepted_at, completed_at
        FROM challenges
        WHERE id = ?
    """, (challenge_id,))

    challenge = cursor.fetchone()
    conn.close()
    return challenge


def get_pending_challenges_for_player(discord_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, challenger_name, opponent_name, game, wager, status, created_at
        FROM challenges
        WHERE opponent_id = ?
        AND status = 'pending'
        ORDER BY created_at ASC
    """, (str(discord_id),))

    challenges = cursor.fetchall()
    conn.close()
    return challenges


def accept_challenge(challenge_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE challenges
        SET status = 'accepted',
            accepted_at = ?
        WHERE id = ?
        AND status = 'pending'
    """, (get_now(), challenge_id))

    conn.commit()
    rows_changed = cursor.rowcount
    conn.close()
    return rows_changed > 0


def decline_challenge(challenge_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE challenges
        SET status = 'declined'
        WHERE id = ?
        AND status = 'pending'
    """, (challenge_id,))

    conn.commit()
    rows_changed = cursor.rowcount
    conn.close()
    return rows_changed > 0


def lock_points_for_challenge(challenger_id, opponent_id, wager):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE players
        SET locked_points = locked_points + ?
        WHERE discord_id = ?
    """, (wager, str(challenger_id)))

    cursor.execute("""
        UPDATE players
        SET locked_points = locked_points + ?
        WHERE discord_id = ?
    """, (wager, str(opponent_id)))

    conn.commit()
    conn.close()


def submit_winner_report(challenge_id, reporter_id, winner_id, winner_name):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT challenger_id, opponent_id, status
        FROM challenges
        WHERE id = ?
    """, (challenge_id,))

    challenge = cursor.fetchone()

    if not challenge:
        conn.close()
        return False, "Challenge not found."

    challenger_id, opponent_id, status = challenge

    if status != "accepted":
        conn.close()
        return False, f"This challenge is not accepting winner reports. Current status: {status}."

    if str(reporter_id) == str(challenger_id):
        cursor.execute("""
            UPDATE challenges
            SET challenger_reported_winner_id = ?,
                challenger_reported_winner_name = ?
            WHERE id = ?
        """, (str(winner_id), winner_name, challenge_id))

    elif str(reporter_id) == str(opponent_id):
        cursor.execute("""
            UPDATE challenges
            SET opponent_reported_winner_id = ?,
                opponent_reported_winner_name = ?
            WHERE id = ?
        """, (str(winner_id), winner_name, challenge_id))

    else:
        conn.close()
        return False, "Only players in this challenge can report the winner."

    conn.commit()
    conn.close()
    return True, "Winner report submitted."


def check_match_reports(challenge_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT challenger_reported_winner_id, opponent_reported_winner_id
        FROM challenges
        WHERE id = ?
    """, (challenge_id,))

    reports = cursor.fetchone()
    conn.close()

    if not reports:
        return "missing", None

    challenger_report, opponent_report = reports

    if not challenger_report or not opponent_report:
        return "waiting", None

    if str(challenger_report) == str(opponent_report):
        return "matched", challenger_report

    return "disputed", None


def mark_challenge_disputed(challenge_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE challenges
        SET status = 'disputed'
        WHERE id = ?
        AND status = 'accepted'
    """, (challenge_id,))

    conn.commit()
    rows_changed = cursor.rowcount
    conn.close()
    return rows_changed > 0


def transfer_challenge_points(challenge_id, winner_id, changed_by_name, reason, required_status):
    conn = get_connection()
    cursor = conn.cursor()

    now = get_now()

    cursor.execute("""
        SELECT id, challenger_id, challenger_name, opponent_id, opponent_name,
               game, wager, status
        FROM challenges
        WHERE id = ?
    """, (challenge_id,))

    challenge = cursor.fetchone()

    if not challenge:
        conn.close()
        return False, "Challenge not found."

    cid, challenger_id, challenger_name, opponent_id, opponent_name, game, wager, status = challenge

    if status != required_status:
        conn.close()
        return False, f"Challenge must be {required_status}. Current status: {status}."

    if str(winner_id) == str(challenger_id):
        winner_id = challenger_id
        winner_name = challenger_name
        loser_id = opponent_id
        loser_name = opponent_name
    elif str(winner_id) == str(opponent_id):
        winner_id = opponent_id
        winner_name = opponent_name
        loser_id = challenger_id
        loser_name = challenger_name
    else:
        conn.close()
        return False, "Winner must be one of the two players in the challenge."

    cursor.execute("SELECT points, locked_points FROM players WHERE discord_id = ?", (str(winner_id),))
    winner_data = cursor.fetchone()

    cursor.execute("SELECT points, locked_points FROM players WHERE discord_id = ?", (str(loser_id),))
    loser_data = cursor.fetchone()

    if not winner_data or not loser_data:
        conn.close()
        return False, "One of the players was not found."

    winner_old_points, winner_locked_points = winner_data
    loser_old_points, loser_locked_points = loser_data

    if winner_locked_points < wager or loser_locked_points < wager:
        conn.close()
        return False, "Locked points are lower than the wager. Manual admin correction may be needed."

    winner_new_points = winner_old_points + wager
    loser_new_points = max(loser_old_points - wager, 0)
    loser_status = "eliminated" if loser_new_points == 0 else "active"

    cursor.execute("""
        UPDATE players
        SET points = ?,
            locked_points = locked_points - ?,
            inactive_streak = 0,
            last_point_change = ?,
            last_inactivity_penalty = NULL
        WHERE discord_id = ?
    """, (winner_new_points, wager, now, str(winner_id)))

    cursor.execute("""
        UPDATE players
        SET points = ?,
            locked_points = locked_points - ?,
            status = ?,
            inactive_streak = 0,
            last_point_change = ?,
            last_inactivity_penalty = NULL
        WHERE discord_id = ?
    """, (loser_new_points, wager, loser_status, now, str(loser_id)))

    log_point_change(cursor, winner_id, winner_name, winner_old_points, winner_new_points, reason, changed_by_name)
    log_point_change(cursor, loser_id, loser_name, loser_old_points, loser_new_points, reason, changed_by_name)

    cursor.execute("""
        UPDATE challenges
        SET status = 'completed',
            completed_at = ?
        WHERE id = ?
    """, (now, challenge_id))

    conn.commit()
    conn.close()

    return True, {
        "winner_name": winner_name,
        "winner_new_points": winner_new_points,
        "loser_name": loser_name,
        "loser_new_points": loser_new_points,
        "wager": wager,
        "game": game,
        "loser_status": loser_status,
        "reason": reason
    }


def complete_challenge_and_transfer_points(challenge_id, winner_id, changed_by_name):
    return transfer_challenge_points(
        challenge_id,
        winner_id,
        changed_by_name,
        f"Both players confirmed Challenge ID {challenge_id}",
        "accepted"
    )


def resolve_dispute_and_transfer_points(challenge_id, winner_id, resolved_by_name, reason):
    return transfer_challenge_points(
        challenge_id,
        winner_id,
        resolved_by_name,
        f"Admin resolved disputed Challenge ID {challenge_id}. Reason: {reason}",
        "disputed"
    )


def admin_adjust_points(discord_id, username, action, amount, reason, changed_by):
    conn = get_connection()
    cursor = conn.cursor()
    now = get_now()

    cursor.execute("SELECT points FROM players WHERE discord_id = ?", (str(discord_id),))
    player = cursor.fetchone()

    if not player:
        conn.close()
        return False, "Player is not registered."

    old_points = player[0]

    if action == "add":
        new_points = old_points + amount
    elif action == "remove":
        new_points = max(old_points - amount, 0)
    elif action == "set":
        new_points = max(amount, 0)
    else:
        conn.close()
        return False, "Action must be add, remove, or set."

    new_status = "eliminated" if new_points == 0 else "active"

    cursor.execute("""
        UPDATE players
        SET points = ?,
            status = ?,
            inactive_streak = 0,
            last_point_change = ?,
            last_inactivity_penalty = NULL
        WHERE discord_id = ?
    """, (new_points, new_status, now, str(discord_id)))

    log_point_change(cursor, discord_id, username, old_points, new_points, f"Admin points {action}: {reason}", changed_by)

    conn.commit()
    conn.close()

    return True, {
        "old_points": old_points,
        "new_points": new_points,
        "status": new_status
    }


def admin_add_or_restore_player(discord_id, username, points, reason, changed_by):
    conn = get_connection()
    cursor = conn.cursor()
    now = get_now()

    cursor.execute("""
        INSERT INTO players (
            discord_id, username, points, locked_points, status,
            inactive_streak, last_point_change, last_inactivity_penalty
        )
        VALUES (?, ?, ?, 0, 'active', 0, ?, NULL)
        ON CONFLICT(discord_id) DO UPDATE SET
            username = excluded.username,
            points = excluded.points,
            locked_points = 0,
            status = 'active',
            inactive_streak = 0,
            last_point_change = excluded.last_point_change,
            last_inactivity_penalty = NULL
    """, (str(discord_id), username, points, now))

    log_point_change(cursor, discord_id, username, 0, points, f"Admin added/restored player: {reason}", changed_by)

    conn.commit()
    conn.close()


def admin_set_player_status(discord_id, status, reason, changed_by):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE players
        SET status = ?,
            locked_points = 0
        WHERE discord_id = ?
    """, (status, str(discord_id)))

    rows_changed = cursor.rowcount
    conn.commit()
    conn.close()

    if rows_changed == 0:
        return False, "Player is not registered."

    return True, f"Player status changed to {status}. Reason: {reason}. Changed by {changed_by}."


def expire_old_pending_challenges():
    conn = get_connection()
    cursor = conn.cursor()

    cutoff = datetime.now(timezone.utc) - timedelta(days=7)

    cursor.execute("""
        UPDATE challenges
        SET status = 'expired'
        WHERE status = 'pending'
        AND created_at <= ?
    """, (cutoff.isoformat(),))

    expired_count = cursor.rowcount
    conn.commit()
    conn.close()
    return expired_count


def apply_inactivity_penalties():
    conn = get_connection()
    cursor = conn.cursor()
    now_dt = datetime.now(timezone.utc)
    now = now_dt.isoformat()

    cursor.execute("""
        SELECT discord_id, username, points, inactive_streak,
               last_point_change, last_inactivity_penalty
        FROM players
        WHERE status = 'active'
    """)

    players = cursor.fetchall()
    results = []

    for discord_id, username, points, inactive_streak, last_point_change, last_inactivity_penalty in players:
        last_valid_change = parse_time(last_point_change)
        last_penalty = parse_time(last_inactivity_penalty)

        check_from = last_penalty if last_penalty else last_valid_change

        if not check_from:
            continue

        if now_dt - check_from >= timedelta(days=7):
            new_streak = inactive_streak + 1
            penalty = 25 * new_streak
            new_points = max(points - penalty, 0)
            new_status = "eliminated" if new_points == 0 else "active"

            cursor.execute("""
                UPDATE players
                SET points = ?,
                    status = ?,
                    inactive_streak = ?,
                    last_inactivity_penalty = ?
                WHERE discord_id = ?
            """, (new_points, new_status, new_streak, now, str(discord_id)))

            log_point_change(
                cursor,
                discord_id,
                username,
                points,
                new_points,
                f"Inactivity penalty week {new_streak}",
                "Culling Game Master"
            )

            results.append((username, penalty, new_points, new_status))

    conn.commit()
    conn.close()
    return results


def create_rule_proposal(proposer_id, proposer_name, rule_text):
    conn = get_connection()
    cursor = conn.cursor()
    now = get_now()

    cursor.execute("SELECT points, locked_points FROM players WHERE discord_id = ?", (str(proposer_id),))
    player = cursor.fetchone()

    if not player:
        conn.close()
        return False, "You are not registered."

    points, locked_points = player
    available = points - locked_points

    if available < 100:
        conn.close()
        return False, "You need 100 available points to propose a rule."

    new_points = points - 100

    cursor.execute("""
        UPDATE players
        SET points = ?,
            last_point_change = ?,
            inactive_streak = 0,
            last_inactivity_penalty = NULL
        WHERE discord_id = ?
    """, (new_points, now, str(proposer_id)))

    log_point_change(cursor, proposer_id, proposer_name, points, new_points, "Spent 100 points to propose a rule", "Culling Game Master")

    cursor.execute("""
        INSERT INTO rule_proposals (
            proposer_id, proposer_name, rule_text, status, created_at
        )
        VALUES (?, ?, ?, 'pending', ?)
    """, (str(proposer_id), proposer_name, rule_text, now))

    proposal_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return True, proposal_id


def get_rule_proposal(proposal_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, proposer_id, proposer_name, rule_text, status,
               admin_approved, admin_approved_by, created_at, approved_at
        FROM rule_proposals
        WHERE id = ?
    """, (proposal_id,))

    proposal = cursor.fetchone()
    conn.close()
    return proposal


def approve_rule_as_admin(proposal_id, admin_name):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE rule_proposals
        SET admin_approved = 1,
            admin_approved_by = ?
        WHERE id = ?
        AND status = 'pending'
        AND admin_approved = 0
    """, (admin_name, proposal_id))

    conn.commit()
    rows_changed = cursor.rowcount
    conn.close()
    return rows_changed > 0


def approve_rule_as_player(proposal_id, voter_id, voter_name):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT proposer_id, status FROM rule_proposals WHERE id = ?", (proposal_id,))
    proposal = cursor.fetchone()

    if not proposal:
        conn.close()
        return False, "Rule proposal not found."

    proposer_id, status = proposal

    if status != "pending":
        conn.close()
        return False, f"Rule proposal is not pending. Current status: {status}."

    if str(voter_id) == str(proposer_id):
        conn.close()
        return False, "The proposer cannot count as one of the 3 player approvals."

    cursor.execute("SELECT status FROM players WHERE discord_id = ?", (str(voter_id),))
    player = cursor.fetchone()

    if not player or player[0] != "active":
        conn.close()
        return False, "Only active players can approve rule proposals."

    try:
        cursor.execute("""
            INSERT INTO rule_approvals (proposal_id, voter_id, voter_name, created_at)
            VALUES (?, ?, ?, ?)
        """, (proposal_id, str(voter_id), voter_name, get_now()))
    except sqlite3.IntegrityError:
        conn.close()
        return False, "You already approved this rule proposal."

    conn.commit()
    conn.close()
    return True, "Player approval recorded."


def reject_rule_as_player(proposal_id, voter_id, voter_name):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT status FROM rule_proposals WHERE id = ?", (proposal_id,))
    proposal = cursor.fetchone()

    if not proposal:
        conn.close()
        return False, "Rule proposal not found."

    status = proposal[0]

    if status != "pending":
        conn.close()
        return False, f"Rule proposal is not pending. Current status: {status}."

    try:
        cursor.execute("""
            INSERT INTO rule_rejections (proposal_id, voter_id, voter_name, created_at)
            VALUES (?, ?, ?, ?)
        """, (proposal_id, str(voter_id), voter_name, get_now()))
    except sqlite3.IntegrityError:
        conn.close()
        return False, "You already voted no on this rule proposal."

    conn.commit()
    conn.close()
    return True, "No vote recorded."


def get_rule_counts(proposal_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT admin_approved
        FROM rule_proposals
        WHERE id = ?
    """, (proposal_id,))
    proposal = cursor.fetchone()

    cursor.execute("""
        SELECT COUNT(*)
        FROM rule_approvals
        WHERE proposal_id = ?
    """, (proposal_id,))
    player_yes_count = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM rule_rejections
        WHERE proposal_id = ?
    """, (proposal_id,))
    player_no_count = cursor.fetchone()[0]

    conn.close()

    if not proposal:
        return None

    return proposal[0], player_yes_count, player_no_count


def approve_rule_if_ready(proposal_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT admin_approved
        FROM rule_proposals
        WHERE id = ?
        AND status = 'pending'
    """, (proposal_id,))
    proposal = cursor.fetchone()

    if not proposal:
        conn.close()
        return False

    admin_approved = proposal[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM rule_approvals
        WHERE proposal_id = ?
    """, (proposal_id,))
    player_count = cursor.fetchone()[0]

    if admin_approved == 1 and player_count >= 3:
        cursor.execute("""
            UPDATE rule_proposals
            SET status = 'approved',
                approved_at = ?
            WHERE id = ?
        """, (get_now(), proposal_id))
        conn.commit()
        conn.close()
        return True

    conn.close()
    return False


def fail_rule_proposal(proposal_id, failed_by_name, reason):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE rule_proposals
        SET status = 'failed'
        WHERE id = ?
        AND status = 'pending'
    """, (proposal_id,))

    conn.commit()
    rows_changed = cursor.rowcount
    conn.close()

    if rows_changed == 0:
        return False, "Rule proposal was not found or is not pending."

    return True, {
        "failed_by": failed_by_name,
        "reason": reason
    }