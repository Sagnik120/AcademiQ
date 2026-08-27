import httpx
import asyncio
import json

async def test_grading():
    url = "http://localhost:8002/grade"
    payload = {
        "question": "What is the powerhouse of the cell and why?",
        "student_answer": "The powerhouse is the mitochondria. It makes energy.",
        "reference_answer": "Mitochondria is the powerhouse of the cell because it generates most of the cell's supply of ATP, used as a source of chemical energy.",
        "max_marks": 5.0,
        "grading_rubric": "1 mark for identifying mitochondria. 4 marks for explaining energy/ATP."
    }
    print("Testing /grade endpoint...")
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=payload)
            if response.status_code == 200:
                print("✅ /grade Success!")
                print(json.dumps(response.json(), indent=2))
            else:
                print(f"❌ /grade Failed with {response.status_code}")
                print(response.text)
    except Exception as e:
        print(f"❌ Exception: {repr(e)}")

if __name__ == "__main__":
    asyncio.run(test_grading())
