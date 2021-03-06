import html.parser
import time

from twython import Twython

class NoConfig(Exception):
    pass

class TwitterPlugin:
    def __init__(self, bot):
        self.bot = bot

    def startup(self, config):
        if config is None:
            raise NoConfig

        self.API_KEY = config["API_KEY"]
        self.API_SECRET = config["API_SECRET"]
        self.OAUTH_TOKEN = config["OAUTH_TOKEN"]
        self.OAUTH_SECRET = config["OAUTH_SECRET"]

        self.username = config["username"]
        self.userid = config["userid"]

        self.allowed_posters = config["allowed_posters"]

        self.twitter = Twython(self.API_KEY, self.API_SECRET,
                               self.OAUTH_TOKEN, self.OAUTH_SECRET)

        self.bot.registerCommand("tweets", self.cmd_tweets)
        self.bot.registerCommand("tweet", self.cmd_post)

        self.HTMLParser = html.parser.HTMLParser()

    def shutdown(self):
        pass


    def reply(self, text):
        self.bot.reply(self.HTMLParser.unescape(text))


    def cmd_post(self, issuedBy, data):
        """- post a tweet"""
        if issuedBy not in self.allowed_posters:
            self.reply("You are not allowed to post a tweet.")
            return

        if not data:
            self.reply("Tweet cannot be empty!")
            return

        self.twitter.update_status(status = data)


    def cmd_tweets(self, issuedBy, data):
        """- lists up to 200 tweets from the configured user"""
        r = self.twitter.get_user_timeline(user_id = self.userid,
            count = 200, include_rts = False)

        reply = []
        for tweet in r:
            if not data or data and data.lower() in tweet["text"].lower():
                reply.append(tweet["text"])

        for tweet in reply:
            self.reply(tweet)

            # This is a silly way to rate-limit, another way must be found
            time.sleep(1)