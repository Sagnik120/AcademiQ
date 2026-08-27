import httpx
import asyncio
import json
from test_pdf import create_dummy_pdf

async def test_pipeline():
    print("🚀 Starting End-to-End Pipeline Test")
    
    async with httpx.AsyncClient(timeout=60) as client:
        # Step 1: Extract PDF
        print("\n[1/3] Extracting PDF...")
        b64_pdf = create_dummy_pdf()
        pdf_res = await client.post("http://localhost:8002/extract-pdf", json={"file_bytes": b64_pdf})
        if pdf_res.status_code != 200:
            print("❌ Pipeline failed at PDF extraction")
            return
        content = pdf_res.json().get("text", "")
        print(f"✅ Extracted text length: {len(content)}")
        
        # Step 2: Generate Questions
        print("\n[2/3] Generating Questions...")
        gen_payload = {
            "content": content,
            "mcq_count": 0,
            "msq_count": 0,
            "text_count": 1,
            "difficulty_hint": "beginner"
        }
        gen_res = await client.post("http://localhost:8002/generate-questions", json=gen_payload)
        if gen_res.status_code != 200:
            print("❌ Pipeline failed at Question Generation")
            return
        
        questions = gen_res.json().get("questions", [])
        if not questions:
            print("❌ Pipeline failed: No text questions generated")
            return
            
        q = questions[0]
        question_text = q.get("question_text")
        ref_answer = q.get("reference_answer")
        marks = q.get("marks", 5.0)
        
        print(f"✅ Generated Question: {question_text}")
        print(f"✅ Reference Answer: {ref_answer}")
        
        # Step 3: Grade Answer
        print("\n[3/3] Grading Student Answer...")
        grade_payload = {
            "question": question_text,
            "student_answer": "It is a test document.",
            "reference_answer": ref_answer,
            "max_marks": marks
        }
        grade_res = await client.post("http://localhost:8002/grade", json=grade_payload)
        if grade_res.status_code != 200:
            print("❌ Pipeline failed at Grading")
            return
            
        grade_data = grade_res.json()
        print(f"✅ Grading complete. Marks awarded: {grade_data.get('marks_awarded')}/{marks}")
        print("✅ Pipeline Test Successful!")

if __name__ == "__main__":
    asyncio.run(test_pipeline())
