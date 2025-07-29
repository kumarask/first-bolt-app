from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from datetime import datetime
import time
from collections import defaultdict
import logging
logging.basicConfig(level=logging.DEBUG, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Slack app
app = App(token="")
socket_token =""

@app.command("/statistics")
def summarize_threads(ack, respond, command):
    ack()

    channel_id = command['channel_id']
    logger.debug(f"Command received: {command}")
    # Fix date range
    start_date = datetime(2025, 7, 5)
    end_date = datetime(2025, 7, 28, 23, 59, 59)
    logger.debug(f"start date : {start_date} End date : {end_date}")
    oldest_ts = time.mktime(start_date.timetuple())
    latest_ts = time.mktime(end_date.timetuple())
    logger.info(f"time stamp {oldest_ts}  {latest_ts}")

    try:
        total_threads = 0
        reaction_counts = defaultdict(lambda: defaultdict(int))  # reaction_counts[user][reaction] = count
        threads_without_check = []
        next_cursor = None

        while True:
            result = app.client.conversations_history(
                channel=channel_id,
                oldest=oldest_ts,
                latest=latest_ts,
                limit=200,
                cursor=next_cursor
            )
            messages = result.get("messages", [])
            for msg in messages:
                total_threads += 1
                reactions = msg.get("reactions", [])
                has_check = False
                all_reactors = set()
                for reaction in reactions:
                    name = reaction["name"]
                    for user_id in reaction.get("users", []):
                        try:
                            user_info = app.client.users_info(user=user_id)
                            profile = user_info["user"].get("profile", {})
                            display_name = profile.get("display_name") or user_info["user"]["name"]
                        except Exception:
                            display_name = f"<@{user_id}>"
                        reaction_counts[display_name][name] += 1
                        all_reactors.add(display_name)
                    if name in ["green_check_mark", "white_check_mark"]:
                        has_check = True
                if not has_check:
                    permalink_resp = app.client.chat_getPermalink(channel=channel_id, message_ts=msg.get("ts"))
                    permalink = permalink_resp.get("permalink", "No Link")
                    message_time = datetime.fromtimestamp(float(msg.get("ts"))).strftime('%Y-%m-%d %H:%M:%S')
                    threads_without_check.append({
                        "link": permalink,
                        "time": message_time,
                        "reactors": list(all_reactors)
                    })
            next_cursor = result.get("response_metadata", {}).get("next_cursor")
            if not next_cursor:
                break

        # Prepare summary per user
        summary_lines = []
        for user, reactions in sorted(reaction_counts.items(), key=lambda x: sum(x[1].values()), reverse=True):
            checks = reactions.get("green_check_mark", 0) + reactions.get("white_check_mark", 0)
            eyes = reactions.get("eyes", 0)
            others = sum(v for k, v in reactions.items() if k not in ["green_check_mark", "white_check_mark", "eyes"])
            summary_lines.append(f"• *{user}*: ✅ {checks} | 👀 {eyes} | Other: {others}")

        # Prepare unresolved threads
        lines = []
        index = 1
        max_links = 50
        for thread in threads_without_check:
            if index > max_links:
                break
            reactors = ", ".join(thread["reactors"]) if thread["reactors"] else "No reactions"
            lines.append(f"{index}. *Created On:* {thread['time']} | *Acknowledged By:* {reactors} | <{thread['link']}|Link>")
            index += 1

        respond(f"""
📊 *Thread Summary (July 2025)*

🧵 Total Slack Requests: *{total_threads}*
🚫 Pending: *{len(threads_without_check)}*

👤 *Engineer Reaction Stats:*
{chr(10).join(summary_lines)}

{chr(10).join(lines) if lines else '🎉 All Slack Requests are Resolved!'}

_Only showing first {max_links} links._
""")

    except Exception as e:
        print(f"❌ Error: {e}")
        respond(f"Error: {str(e)}")

# Run the app
if __name__ == "__main__":
    handler = SocketModeHandler(app, socket_token)
    handler.start()
