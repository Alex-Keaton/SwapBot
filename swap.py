import re
import json
import praw
import time

subreddit_name = 'funkoswap'
FNAME_comments = 'database/active_comments-' + subreddit_name + '.txt'
FNAME_swaps = 'database/swaps-' + subreddit_name + ".json"

f = open("config.txt", "r")
info = f.read().splitlines()
f.close()

client_id = info[0]
client_secret = info[1]
bot_username = info[2]
bot_password = info[3]

def get_prev_ids():
	try:
		f = open(FNAME_comments, "r")
		ids = f.read().splitlines()
		f.close()
		return ids
	except:
		f = open(FNAME_comments, "w")
		f.write("")
		f.close()
		return []

# Method for giving credit to users when they do a trade.
# Returns True if credit was given, False otherwise
def update_database(author1, author2, swap_data, post_id):
	author1 = str(author1).lower()  # Create strings of the user names for keys and values
	author2 = str(author2).lower()

	# Default generic value for swaps
	message = " - https://www.reddit.com/r/" + subreddit_name + "/comments/" + post_id
	if author1 not in swap_data:  # If we have not seen this user before in swap, make a new entry for them
		swap_data[author1] = [author2 + message]
	else:  # If we have seen them before, we want to make sure they didnt already get credit for this swap (same user and same post)
		if author2 + message in swap_data[author1]:
			return False
		swap_data[author1].append(author2 + message)
	if author2 not in swap_data:  # Same as above but for the other user. too lazy to put this in a nice loop and the user case will never expand past two users
                swap_data[author2] = [author1 + message]
        else:
		if author1 + message in swap_data[author2]:
			return False
                swap_data[author2].append(author1 + message)
	return True  # If all went well, return true

def update_flair(author1, author2, sub, swap_data):
	author1 = str(author1).lower()  # Create strings of the user names for keys and values
	author2 = str(author2).lower()

	flairs = reddit.subreddit(subreddit_name).flair(limit=None)
	# Loop over each author and change their flair
	for author in [author1, author2]:
		for flair in flairs:  # This is stupid but it's the only way I can figure to get a specific user's flair, so here we are
			if not flair['user'].name.lower() == author:
				continue
			try:  # once we found the user in question, get their old flair css, add 1, and convert back to a string
				css = str(len(swap_data[author]))
			except:  # If they have no flair, default them to 1
				css = "1"
		# And tthen update their flair
		reddit.subreddit(subreddit_name).flair.set(author, flair['flair_text'], css)

def dump(to_write):
	f = open(FNAME_comments, "w")
	f.write("\n".join(to_write))
	f.close()

# IDK, I needed this according to stack overflow.
def ascii_encode_dict(data):
	ascii_encode = lambda x: x.encode('ascii') if isinstance(x, unicode) else x
	return dict(map(ascii_encode, pair) for pair in data.items())

# Function to load the swap DB into memory
def get_swap_data():
#	try:
	if True:
		with open(FNAME_swaps) as json_data: # open the funko-shop's data
			funko_store_data = json.load(json_data, object_hook=ascii_encode_dict)
		return funko_store_data
#	except:
	else:
		f = open(FNAME_swaps, "w")
		f.write("{}")
		f.close()
		return {}

# Writes the json local file... dont touch this.
def dump_json(swap_data):
	with open(FNAME_swaps, 'w') as outfile:  # Write out new data
		outfile.write(str(json.dumps(swap_data))
			.replace("'", '"')
			.replace(', u"', ', "')
			.replace('[u"', '["')
			.replace('{u"', '{"')
			.encode('ascii','ignore'))


reddit = praw.Reddit(client_id=client_id, client_secret=client_secret, user_agent='UserAgent', username=bot_username, password=bot_password)
sub = reddit.subreddit(subreddit_name)

swap_data = get_swap_data()  # Gets the swap data for all users
ids = get_prev_ids()  # Ids of previously seen comments that have not been finished
to_write = []  # What we will eventually write out to the local file
comments = []  # Stores comments from both sources of Ids
messages = []  # Want to catch everything else for replying

# Get comments from locally saved ids
for comment_id in ids:
	try:
		comments.append(reddit.comment(comment_id))
	except:  # If we fail, the user deleted their comment or account, so skip
		pass

# Get comments from username mentions
for message in reddit.inbox.unread():
	message.mark_read()
	if message.was_comment and message.subject == "username mention":
		try:
			comments.append(reddit.comment(message.id))
		except:  # if this fails, the user deleted their account or comment so skip it
			pass
	else:
		messages.append(message)

comments = list(set(comments))  # Dedupe just in case we get duplicates from the two sources

# Process comments
for comment in comments:
	comment.refresh()  # Don't know why this is required but it doesnt work without it so dont touch it
	time_made = comment.created
	if time.time() - time_made > 3 * 24 * 60 * 60:  # if this comment is more than three days old
		try:
			comment.reply("This comment has been around for more than 3 days without a response and will no longer be tracked. If you wish to continue tracking, please make a new top level comment tagging both this bot and the person you traded with. Thanks!")
		except Exception as e:
			print("\n\n" + str(time.time()) + "\n" + str(e))  # comment was probably deleted
		continue  # don't do anything to it, and don't add it to check later (let it finally drop off)
	OP = comment.parent().author  # Get the OP of the post (because one of the users in the comment chain must be the OP)
	author1 = comment.author  # Author of the top level comment
	comment_word_list = [str(x) for x in comment.body.lower().replace("\n", " ").split(" ")]  # all words in the top level comment
	desired_author2_string = ""
	for word in comment_word_list:  # We try to find the person being tagged in the top level comment
		if "u/" in word and bot_username.lower() not in word:
			desired_author2_string = word
			if desired_author2_string[0] == "/":  # Sometimes people like to add a / to the u/username
				desired_author2_string = desired_author2_string[1:]
			if desired_author2_string[-1] == ".":
				desired_author2_string = desired_author2_string[:-1]
			break
	if not desired_author2_string:
		print("\n\n" + str(time.time()) + "\n" + "Unable to find a username in " + str(comment_word_list) + " for post " + comment.parent().id)
		try:
			comment.reply("You did not tag anyone other than this bot in your comment. Please post a new top level comment tagging this bot and the person you traded with to get credit for the trade.")
		except Exception as e:  # Comment was probably deleted
			print("\n\n" + str(time.time()) + "\n" + e)
		continue
	author2 = ""  # Set to null for now so we can see if we were successful in finding any children comments
	correct_reply = None
	for reply in comment.replies.list():
		if not 'confirmed' in reply.body.lower():  # if a reply does not say confirmed, skip it
			continue
		potential_author2_string = "u/"+str(reply.author).lower()
		if not potential_author2_string == desired_author2_string:
			continue
		if str(author1).lower() == potential_author2_string:  # They can't get credit for swapping with themselves
			continue
		author2 = reply.author
		correct_reply = reply
		break
	if author2:  # If we found any correct looking comments
		if OP in [author1, author2]:  # make sure at least one of them is the OP for the post
			credit_give = update_database(author1, author2, swap_data, comment.parent().id)
			if credit_give:
				try:
					correct_reply.reply("Added")
				except Exception as e:  # Comment was orobably deleted
					print("\n\n" + str(time.time()) + "\n" + e)
				update_flair(author1, author2, sub, swap_data)
			else:
				try:
					correct_reply.reply("You already got credit for this trade. Please contact the moderators if you think this is an error.")
				except Exception as e:  # Comment was probably deleted
					print("\n\n" + str(time.time()) + "\n" + e)
	else:  # If we found no correct looking comments, let's come back to it later
		to_write.append(str(comment.id))

dump(to_write)  # Save off any unfinished tags
dump_json(swap_data)  # Dump out swap data now that we have updated it as well

# This is for if anyone sends us a message requesting swap data
for message in messages:
	text = (message.body + " " +  message.subject).replace("\n", " ").split(" ")  # get each unique word
	username = ""  # This will hold the username in question
	for word in text:
		if 'u/' in word.lower():  # if we have a username
			username = word.lower()[2:]  # Save the username and break early
			break
	if not username:  # If we didn't find a username, let them know and continue
		message.reply("Hi there,\n\nYou did not specify a username to check. Please ensure that you have a user name, such as u/FreddySwapBot, in the body of the message you just sent me. Please feel free to try again. Thanks!")
		continue
	final_text = ""
	try:
		trades = swap_data[username]
	except:  # if that user has not done any trades, we have no info for them.
		message.reply("Hello,\n\nu/" + username + " has not had any swaps yet.")
		continue

	legacy_count = 0  # Use this to track the number of legacy swaps someone has
	for trade in trades:
		if trade == "LEGACY TRADE":
			legacy_count += 1
		else:
			final_text += "*  u/" + trade + "\n\n"

	if legacy_count > 0:
		final_text = "* " + str(legacy_count) + " Legacy Trades (trade done before this bot was created)\n\n" + final_text

	message.reply("Hello,\n\nu/" + username + " has had the following " + str(len(trades)) + " swaps:\n\n" + final_text)

