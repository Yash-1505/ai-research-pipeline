import os
import json
import time
from datetime import datetime
from google import genai

def run_pipeline():
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    freq = os.environ.get("RESEARCH_FREQUENCY", "daily")
    
    prompts = {
        "daily": "Perform a scan of the last 24 hours of AI developments. Focus on breaking news, repository updates, and model releases.",
        "weekly": "Analyze the past week of AI research papers and major framework releases. Summarize key trends and breakthroughs.",
        "monthly": "Conduct a deep-dive report on the month's AI evolution. Include industry shifts and SOTA model benchmarks."
    }
    
    interaction = client.interactions.create(
        input=prompts[freq],
        agent='deep-research-pro-preview-04-2026',
        background=True
    )
    
    while True:
        interaction = client.interactions.get(interaction.id)
        if interaction.status == "completed":
            report_text = interaction.outputs[-1].text
            break
        elif interaction.status == "failed":
            raise Exception("Research agent failed")
        time.sleep(30)

    summary_prompt = (
        f"Convert this {freq} research into Markdown and a JSON object. "
        "The JSON must have keys: 'title', 'timestamp', 'summary', 'key_takeaways', 'sources'.\n\n"
        f"Research Content: {report_text}"
    )
    
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=summary_prompt
    )
    
    raw_output = response.text
    try:
        md_content = raw_output.split("```json")[0].replace("```markdown", "").strip()
        json_str = raw_output.split("```json")[1].split("```")[0].strip()
    except IndexError:
        md_content = raw_output
        json_str = json.dumps({"error": "Failed to parse structured JSON"})
    
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
