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
        "daily": "Perform a rapid scan of the last 24 hours of AI developments. Focus on model releases and major GitHub updates.",
        "weekly": "Analyze the past week of AI research papers and framework updates. Identify the 3 most significant shifts.",
        "monthly": "Comprehensive monthly AI state-of-the-union. Include benchmarks, industry consolidation, and SOTA leaderboards."
    }
    
    print(f"🚀 Starting {freq} research using Deep Research Agent...")
    
    # Starting the Deep Research Agent (Using the 2026 stable identifier)
    interaction = client.interactions.create(
        input=prompts[freq],
        agent='deep-research-pro-preview-12-2025',
        background=True,
        store=True
    )
    
    # Polling for completion
    while True:
        interaction = client.interactions.get(interaction.id)
        if interaction.status == "completed":
            report_text = interaction.outputs[-1].text
            break
        elif interaction.status == "failed":
            raise Exception(f"Research agent failed: {interaction.error}")
        
        print(f"⏳ Researching... Status: {interaction.status} (ID: {interaction.id})")
        time.sleep(30)

    # Summarize using the correct 2026 model name: gemini-3-flash
    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=4, max=60))
    def generate_formatted_output(text):
        print("📝 Generating final Markdown and JSON...")
        summary_prompt = (
            f"Act as a research archivist. Convert the following {freq} research into a clean Markdown report "
            "and a JSON object with keys: 'title', 'timestamp', 'summary', 'key_takeaways', 'sources'.\n\n"
            f"Content: {text}"
        )
        return client.models.generate_content(
            model="gemini-3-flash", 
            contents=summary_prompt
        )

    try:
        response = generate_formatted_output(report_text)
        raw_output = response.text
        
        try:
            # Separating Markdown from JSON
            md_content = raw_output.split("```json")[0].replace("```markdown", "").strip()
            json_str = raw_output.split("```json")[1].split("```")[0].strip()
            json.loads(json_str) # Verify validity
        except Exception:
            md_content = raw_output
            json_str = json.dumps({
                "title": f"{freq.capitalize()} AI Research",
                "timestamp": datetime.now().isoformat(),
                "summary": "Report generated; JSON extraction failed.",
                "error": "Formatting mismatch"
            })

        # Archiving
        now = datetime.now()
        path = f"archive/{now.year}/{now.strftime('%m')}/{freq}"
        os.makedirs(path, exist_ok=True)
        file_prefix = f"{now.strftime('%Y-%m-%d')}"
        
        with open(f"{path}/{file_prefix}_report.md", "w") as f:
            f.write(md_content)
        with open(f"{path}/{file_prefix}_data.json", "w") as f:
            f.write(json_str)
        
        print(f"✅ Success! Data archived in {path}")

    except Exception as e:
        print(f"❌ Processing failed: {e}")
        # Emergency save to prevent data loss
        os.makedirs("archive/temp", exist_ok=True)
        with open(f"archive/temp/raw_output_{int(time.time())}.txt", "w") as f:
            f.write(report_text)
        raise

if __name__ == "__main__":
    run_pipeline()
