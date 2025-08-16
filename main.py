from dotenv import load_dotenv
import os
import logging
from bot import bot


def main():

    logging.basicConfig(
        format="%(asctime)s %(levelname)s : %(message)s",
        level = logging.INFO,
    )
    load_dotenv()
    token = os.environ["DISCORD_TOKEN"]
    if not token:
        raise RuntimeError(
            "Bot token not found"
        )
    
    logging.info("Starting Bot...")
    bot.run(token)

if __name__ == "__main__":
    main()


