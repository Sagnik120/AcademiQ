import httpx
import asyncio
import json

async def test_generation():
    url = "http://localhost:8002/generate-questions"
    payload = {
        "content": "Photosynthesis is the process used by plants, algae and certain bacteria to harness energy from sunlight and turn it into chemical energy.",
        "mcq_count": 1,
        "msq_count": 1,
        "text_count": 1,
        "difficulty_hint": "beginner"
    }
    print("Testing /generate-questions endpoint...")
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(url, json=payload)
            if response.status_code == 200:
                print("✅ /generate-questions Success!")
                print(json.dumps(response.json(), indent=2))
            else:
                print(f"❌ /generate-questions Failed with {response.status_code}")
                print(response.text)
    except Exception as e:
        print(f"❌ Exception: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_generation())
