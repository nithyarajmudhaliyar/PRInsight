import asyncio
import httpx
from datetime import datetime

async def main():
    async with httpx.AsyncClient() as httpx_client:
        url = "https://api.github.com/repos/zulip/zulip/pulls"
        params = {"state": "open", "per_page": 100, "sort": "updated", "direction": "desc"}
        
        print(f"Exact URL: {url}")
        print(f"Query Parameters: {params}")
        
        response = await httpx_client.get(url, params=params)
        
        print(f"Status: {response.status_code}")
        print(f"Link Header: {response.headers.get('link')}")
        
        data = response.json()
        print(f"Total PRs returned: {len(data)}")
        
        if not data:
            return
            
        # Verify complete list is sorted by updated_at descending
        is_sorted = True
        for i in range(len(data) - 1):
            date1 = datetime.fromisoformat(data[i]['updated_at'].replace('Z', '+00:00'))
            date2 = datetime.fromisoformat(data[i+1]['updated_at'].replace('Z', '+00:00'))
            if date1 < date2:
                is_sorted = False
                print(f"Sort violation at index {i}: {data[i]['updated_at']} < {data[i+1]['updated_at']}")
                break
        print(f"Is list strictly sorted by updated_at descending? {is_sorted}")

        # Find the PR from 2021 (or the oldest PR by updated_at)
        oldest_updated_pr = min(data, key=lambda pr: datetime.fromisoformat(pr['updated_at'].replace('Z', '+00:00')))
        idx = data.index(oldest_updated_pr)
        
        print("\n--- PR INVESTIGATION ---")
        print(f"PR Number: {oldest_updated_pr['number']}")
        print(f"created_at: {oldest_updated_pr['created_at']}")
        print(f"updated_at: {oldest_updated_pr['updated_at']}")
        print(f"state: {oldest_updated_pr['state']}")
        print(f"Position (index) in response: {idx}")
        
        if idx > 0:
            print(f"Previous PR (idx {idx-1}) updated_at: {data[idx-1]['updated_at']}")
        if idx < len(data) - 1:
            print(f"Next PR (idx {idx+1}) updated_at: {data[idx+1]['updated_at']}")

if __name__ == "__main__":
    asyncio.run(main())
