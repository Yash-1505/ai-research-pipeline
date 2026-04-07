import os
import json
import time
from datetime import datetime
from google import genai
from tenacity import retry, stop_after_attempt, wait_exponential

def run_pipeline():
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    freq = os.environ.get("RESEARCH_FREQUENCY", "daily")
    
    prompts = {
        "daily": "Scan the last 24 hours of AI developments. Focus on breaking news and GitHub repo updates.",
        "weekly": "Analyze the past week of AI research papers and major framework releases. Identify 3 major trends.",
        "monthly": "Deep-dive report on this month's AI evolution. Include industry shifts and SOTA model benchmarks."
    }
    
    # 1. Start the Deep Research Agent
    print(f"🚀 Starting {freq} research task...")
    interaction = client.interactions.create(
        input=prompts[freq],
        agent='deep-research-pro-preview-12-2025',
        background=True,
        store=True
    )
    
    # 2. Poll for completion
    while True:
        interaction = client.interactions.get(interaction.id)
        if interaction.status == "completed":
            report_text = interaction.outputs[-1].text
            break
        elif interaction.status == "failed":
            raise Exception(f"Research agent failed: {interaction.error}")
        
        print(f"⏳ Status: {interaction.status}... (Task ID: {interaction.id})")
        time.sleep(30)

    # 3. Summarize with Retry Logic to avoid 429 errors
    # Using gemini-1.5-flash as it has higher Free Tier quotas than 2.0-flash
    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=4, max=60))
    def generate_summary(text):
        print("📝 Generating summary and JSON data...")
        summary_prompt = (
            f"Format this {freq} research into a Markdown report and a JSON object. "
            "JSON keys: 'title', 'timestamp', 'summary', 'key_takeaways', 'sources'.\n\n"
            f"Content: {text}"
        )
        return client.models.generate_content(
            model="gemini-1.5-flash",
            contents=summary_prompt
        )

    try:
        response = generate_summary(report_text)
        raw_output = response.text
        
        # 4. Parse output
        try:
            md_content = raw_output.split("```json")[0].replace("```markdown", "").strip()
            json_str = raw_output.split("```json")[1].split("```")[0].strip()
        except (IndexError, ValueError):
            md_content = raw_output
            json_str = json.dumps({
                "title": f"{freq.capitalize()} AI Research",
                "timestamp": datetime.now().isoformat(),
                "summary": "Full report saved in markdown. JSON parsing failed.",
                "error": "Formatting mismatch"
            })

        # 5. Save to Archive
        now = datetime.now()
        path = f"archive/{now.year}/{now.strftime('%m')}/{freq}"
        os.makedirs(path, exist_ok=True)
        
        file_prefix = f"{now.strftime('%Y-%m-%d')}"
        
        with open(f"{path}/{file_prefix}_report.md", "w") as f:
            f.write(md_content)
            
        with open(f"{path}/{file_prefix}_data.json", "w") as f:
            f.write(json_str)
        
        print(f"✅ Success! Archived in {path}")

    except Exception as e:
        print(f"❌ Summary failed after retries: {e}")
        # Emergency save of raw data so research isn't lost
        os.makedirs("archive/debug", exist_ok=True)
        with open(f"archive/debug/raw_failed_{int(time.time())}.txt", "w") as f:
            f.write(report_text)
        raise

if __name__ == "__main__":
    run_pipeline()
