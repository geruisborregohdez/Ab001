"""
Example: Connect to the Ab001 MCP server programmatically.

Install: pip install mcp
Run:     python examples/mcp_client_example.py

By default connects to http://localhost/mcp/sse (via Nginx).
Set MCP_URL env var to point to a different host.
"""
import asyncio
import json
import os

from mcp import ClientSession
from mcp.client.sse import sse_client

MCP_URL = os.getenv("MCP_URL", "http://localhost/mcp/sse")


async def main():
    print(f"Connecting to MCP server at {MCP_URL}\n")

    async with sse_client(MCP_URL) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # List available tools
            tools_response = await session.list_tools()
            print("Available tools:")
            for tool in tools_response.tools:
                print(f"  - {tool.name}: {tool.description}")
            print()

            # Example 1: List all customers
            print("=== List customers ===")
            result = await session.call_tool("list_customers", {})
            customers = json.loads(result.content[0].text)
            print(json.dumps(customers, indent=2))
            print()

            # Example 2: Create a customer
            print("=== Create a customer ===")
            result = await session.call_tool("create_customer", {
                "name": "Acme Corp",
                "email": "billing@acme.com",
                "phone": "555-0100",
                "address_street": "1 Acme Blvd",
                "address_city": "Springfield",
                "address_state": "IL",
                "address_zip": "62701",
            })
            customer = json.loads(result.content[0].text)
            print(json.dumps(customer, indent=2))
            customer_id = customer["id"]
            print()

            # Example 3: Create a service for the customer
            print("=== Create a service ===")
            result = await session.call_tool("create_service", {
                "customer_id": customer_id,
                "name": "HVAC Maintenance",
                "description": "Annual HVAC inspection and filter replacement",
                "cost": 85.00,
                "price": 150.00,
            })
            service = json.loads(result.content[0].text)
            print(json.dumps(service, indent=2))
            service_id = service["id"]
            print()

            # Example 4: Complete the service
            print("=== Complete the service ===")
            result = await session.call_tool("complete_service", {"service_id": service_id})
            completed = json.loads(result.content[0].text)
            print(f"Status: {completed['status']}, Completed: {completed['completed_date']}")
            print()

            # Example 5: Create an invoice
            print("=== Create invoice ===")
            result = await session.call_tool("create_invoice", {
                "customer_id": customer_id,
                "service_ids": [service_id],
            })
            invoice = json.loads(result.content[0].text)
            print(json.dumps(invoice, indent=2))
            invoice_id = invoice["id"]
            print()

            # Example 6: Send to QuickBooks (stub)
            print("=== Send invoice to QuickBooks ===")
            result = await session.call_tool("send_invoice_to_quickbooks", {"invoice_id": invoice_id})
            qb_result = json.loads(result.content[0].text)
            print(json.dumps(qb_result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
