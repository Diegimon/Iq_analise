from telethon import TelegramClient
import os

TELEGRAM_API_ID = int(os.getenv("TELEGRAM_API_ID", "29194173"))
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH", "aa6eac958b72727ff8802895a106a74c")
SESSION_NAME = "get_group_id_session"

async def main():
    client = TelegramClient(SESSION_NAME, TELEGRAM_API_ID, TELEGRAM_API_HASH)
    await client.start()

    async for dialog in client.iter_dialogs():
        if dialog.is_group or dialog.is_channel:
            print(f"Nome: {dialog.name}, ID: {dialog.id}")

    await client.disconnect()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
