import asyncio
from playwright.async_api import async_playwright

async def test():
    try:
        print("Starting playwright...")
        p = await async_playwright().start()
        print("Playwright started.")
        await p.stop()
        print("Playwright stopped.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test())
