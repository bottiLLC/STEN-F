from google import genai
import inspect
import asyncio

async def inspect_client():
    client = genai.Client(api_key="TEST")
    print("Client type:", type(client))
    print("Client dir:", dir(client))
    
    print("\nClient.aio type:", type(client.aio))
    print("Client.aio dir:", dir(client.aio))
    
    if hasattr(client.aio, 'close'):
        print("\nclient.aio.close exists")
    else:
        print("\nclient.aio.close DOES NOT exist")
        
    if hasattr(client, 'close'):
        print("client.close exists")

if __name__ == "__main__":
    asyncio.run(inspect_client())
