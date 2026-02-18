
import os
import asyncio
from google import genai
from dotenv import load_dotenv

load_dotenv()

async def main():
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("GOOGLE_API_KEY not found.")
        return

    client = genai.Client(api_key=api_key)
    
    print("Listing models...")
    try:
        # The new SDK might allow listing models via client.models.list() or similar
        # Checking syntax for google.genai
        # It seems the new SDK is 'google-genai', distinct from 'google-generativeai'.
        # Let's try standard list method if available, or just try to generate with a known working model 
        # But list is requested by error message.
        
        # In new SDK v1beta:
        # client.aio.models.list() ?
        
        # Let's try to inspect via help or just try the common pattern
        async for model in client.aio.models.list():
            print(f"Model: {model.name}, Supported methods: {model.supported_generation_methods}")
            
    except Exception as e:
        print(f"Error listing models: {e}")
        # Fallback to old SDK style if installed? No, we see 'google.genai' imported in source.

if __name__ == "__main__":
    asyncio.run(main())
