import os
import json
import time
from datetime import datetime
from google import genai

def run_pipeline():
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    freq = os.environ.get("RESEARCH_FREQUENCY", "daily")
    
    prompts = {
        "daily": "Scan the last 24 hours of AI developments. Focus on breaking news and GitHub repo updates.",
        "weekly": "Analyze the past week of AI research papers and major framework releases. Identify 3 major trends.",
        "monthly": "Deep-dive report on this month's AI evolution. Include industry shifts and SOTA model benchmarks."
    }
    
    # Using the correct stable agent name for 2026
    interaction = client.interactions.create(
        input=prompts[freq],
        agent='deep-research-pro-preview-12-2025',
        background=True,
        config={'store': True}
    )
    
    while True:
        interaction = client.interactions.get(interaction.id)
        if interaction.status == "completed":
            report_text = interaction.outputs[-1].text
            break
        elif interaction.status == "failed":
            raise Exception(f"Research agent failed: {interaction.error}")
        time.sleep(30)

    # Use Gemini 3.1 Flash for efficient summarization and JSON conversion
    summary_prompt = (
        f"Format this {freq} research into a Markdown report and a JSON object. "
        "JSON keys: 'title', 'timestamp', 'summary', 'key_takeaways', 'sources'.\n\n"
        f"Content: {report_text}"
    )
    
    response = client.models.generate_content(
        model="gemini-3.1-flash",
        contents=summary_prompt
    )
    
    raw_output = response.text
    try:
        # Extract content between markdown tags
        md_content = raw_output.split("```json")[0].replace("```markdown", "").strip()
        json_str = raw_output.split("```json")[1].split("```")[0].strip()
    except (IndexError, ValueError):
        md_content = raw_output
        json_str = json.dumps({"error": "JSON parsing failed", "raw": raw_output})
    
    now = datetime.now()
    path = f"archive/{now.year}/{now.strftime('%m')}/{freq}"
    os.makedirs(path, exist_ok=True)
    
    file_prefix = f"{now.strftime('%Y-%m-%d')}"
    
    with open(f"{path}/{file_prefix}_report.md", "w") as f:
        f.write(md_content)
        
    with open(f"{path}/{file_prefix}_data.json", "w") as f:
        f.write(json_str)

if __name__ == "__main__":
    run_pipeline()
