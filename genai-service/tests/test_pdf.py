import httpx
import asyncio
import base64
from reportlab.pdfgen import canvas
import io

def create_dummy_pdf():
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer)
    p.drawString(100, 750, "This is a test PDF document for AcademiQ GenAI service.")
    p.showPage()
    p.save()
    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode("utf-8")

async def test_pdf():
    url = "http://localhost:8002/extract-pdf"
    b64_pdf = create_dummy_pdf()
    
    payload = {
        "file_bytes": b64_pdf
    }
    print("Testing /extract-pdf endpoint...")
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, json=payload)
            if response.status_code == 200:
                print("✅ /extract-pdf Success!")
                print(response.json())
            else:
                print(f"❌ /extract-pdf Failed with {response.status_code}")
                print(response.text)
    except Exception as e:
        print(f"❌ Exception: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_pdf())
