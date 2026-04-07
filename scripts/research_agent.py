import os
import json
import time
from datetime import datetime
from google import genai
from tenacity import retry, stop_after_attempt, wait_exponential

def run_pipeline():
    # Initialize the Gemini Client
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    freq = os.environ.get("RESEARCH_FREQUENCY", "daily")
    
    # 2026 Optimized Prompts
    prompts = {
        "daily": "Perform a high-speed scan of AI news from the last 24 hours. Focus on model weights, GitHub commits, and ecosystem shifts.",
        "weekly": "Analyze the past 7 days of AI research. Identify the 3 most significant papers and their practical implications.",
        "monthly": "Comprehensive monthly AI state-of-the-union. Benchmarks, industry consolidation, and SOTA leaderboards."
    }
    
    print(f"🚀 Starting {freq} research using Gemini 3.1 Pro Deep Research Agent...")
    
    # Using the 2026 Stable Deep Research Agent
    interaction = client.interactions.create(
        input=prompts[freq],
        agent='deep-research-pro-preview-12-2025',
        background=True,
        store=True
    )
    
    # Poll for completion
    while True:
        interaction = client.interactions.get(interaction.id)
        if interaction.status == "completed":
            report_text = interaction.outputs[-1].text
            break
        elif interaction.status == "failed":
            raise Exception(f"Research agent failed: {interaction.error}")
        
        print(f"⏳ Researching... Status: {interaction.status} (ID: {interaction.id})")
        time.sleep(30)

    # Summarize with Gemini 3.1 Flash (Higher Quota & Better Performance)
    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=4, max=60))
    def generate_formatted_output(text):
        print("📝 Generating final Markdown and JSON...")
        summary_prompt = (
            f"Act as a research archivist. Convert the following {freq} research into a clean Markdown report "
            "and a JSON object with keys: 'title', 'timestamp', 'summary', 'key_takeaways', 'sources'.\n\n"
            f"Content: {text}"
        )
        return client.models.generate_content(
            model="gemini-3.1-flash", 
            contents=summary_prompt
        )

    try:
        response = generate_formatted_output(report_text)
        raw_output = response.text
        
        # Parse output into files
        try:
            md_content = raw_output.split("```json")[0].replace("```markdown", "").strip()
            json_str = raw_output.split("```json")[1].split("```")[0].strip()
            # Validate JSON
            json.loads(json_str) 
        except Exception:
            md_content = raw_output
            json_str = json.dumps({
                "title": f"{freq.capitalize()} AI Research",
                "timestamp": datetime.now().isoformat(),
                "summary": "Report generated; JSON structure parsing failed.",
                "error": "Formatting error"
            })

        # Archive Logic: archive/YYYY/MM/frequency/
        now = datetime.now()
        path = f"archive/{now.year}/{now.strftime('%m')}/{freq}"
        os.makedirs(path, exist_ok=True)
        file_prefix = f"{now.strftime('%Y-%m-%d')}"
        
        with open(f"{path}/{file_prefix}_report.md", "w") as f:
            f.write(md_content)
        with open(f"{path}/{file_prefix}_data.json", "w") as f:
            f.write(json_str)
        
        print(f"✅ Success! Archived to {path}")

    except Exception as e:
        print(f"❌ Final processing failed: {e}")
        # Save raw output as fallback so research isn't lost
        os.makedirs("archive/failed_runs", exist_ok=True)
        with open(f"archive/failed_runs/raw_{int(time.time())}.txt", "w") as f:
            f.write(report_text)
        raise

if __name__ == "__main__":
    run_pipeline()
