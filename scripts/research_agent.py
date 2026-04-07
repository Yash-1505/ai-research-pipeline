import os
import json
import time
from datetime import datetime
from google import genai

def run_pipeline():
    # Initialize the Gemini Client
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    
    # Get the frequency from environment variables set by GitHub Actions
    freq = os.environ.get("RESEARCH_FREQUENCY", "daily")
    
    # Define prompts based on frequency
    prompts = {
        "daily": "Scan the last 24 hours of AI developments. Focus on breaking news, model releases, and key GitHub repo updates.",
        "weekly": "Analyze the past week of AI research papers and major framework releases. Identify 3 major trends.",
        "monthly": "Conduct a deep-dive comprehensive report on the month's AI evolution. Include industry shifts and SOTA model benchmarks."
    }
    
    # Start the Deep Research task
    # Note: 'store=True' is used to ensure the interaction is retrievable during polling
    interaction = client.interactions.create(
        input=prompts[freq],
        agent='deep-research-pro-preview-12-2025',
        background=True,
        store=True
    )
    
    print(f"Started {freq} research task. ID: {interaction.id}")
    
    # Poll for completion
    while True:
        interaction = client.interactions.get(interaction.id)
        if interaction.status == "completed":
            # Extract the final report from the outputs
            report_text = interaction.outputs[-1].text
            break
        elif interaction.status == "failed":
            raise Exception(f"Research agent failed: {interaction.error}")
        
        print(f"Status: {interaction.status}... waiting 30 seconds.")
        time.sleep(30)

    # Format the output into Markdown and JSON
    summary_prompt = (
        f"Convert this {freq} research into a clean Markdown report and a JSON object. "
        "The JSON must have keys: 'title', 'timestamp', 'summary', 'key_takeaways', 'sources'.\n\n"
        f"Research Content: {report_text}"
    )
    
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=summary_prompt
    )
    
    # Extract Markdown and JSON from the response
    raw_output = response.text
    try:
        # Split logic to separate Markdown from JSON code blocks
        md_content = raw_output.split("```json")[0].replace("```markdown", "").strip()
        json_str = raw_output.split("```json")[1].split("```")[0].strip()
    except (IndexError, ValueError):
        # Fallback if parsing fails
        md_content = raw_output
        json_str = json.dumps({
            "title": f"{freq.capitalize()} AI Research",
            "timestamp": datetime.now().isoformat(),
            "summary": "Parsing failed, raw content saved in markdown.",
            "error": "Structured JSON block not found"
        })
    
    # Create the archive folder structure: archive/YYYY/MM/frequency/
    now = datetime.now()
    path = f"archive/{now.year}/{now.strftime('%m')}/{freq}"
    os.makedirs(path, exist_ok=True)
    
    file_prefix = f"{now.strftime('%Y-%m-%d')}"
    
    # Save files
    with open(f"{path}/{file_prefix}_report.md", "w") as f:
        f.write(md_content)
        
    with open(f"{path}/{file_prefix}_data.json", "w") as f:
        f.write(json_str)
    
    print(f"Research archived successfully in {path}")

if __name__ == "__main__":
    run_pipeline()
