from ai_service import analyze_document_discrepancies


comparison_rows = [
    {
        "field": "port_of_loading",
        "si": "PORT KLANG (WESTPORT), MALAYSIA",
        "bl": "RUGAO/NANTONG/SHANGHAI, CHINA",
        "result": "MISMATCH",
    },
    {
        "field": "port_of_discharge",
        "si": "HOUSTON, US",
        "bl": "MOMBASA, KENYA",
        "result": "MISMATCH",
    },
    {
        "field": "shipper",
        "si": "ASIA PACIFIC PAPERBOARD TRADING PTE LTD",
        "bl": "ASIA PACIFIC PAPERBOARD TRADING PTE LTD",
        "result": "MATCH",
    },
    {
        "field": "consignee",
        "si": "SAFQA LIMITED",
        "bl": "SAFQA LIMITED",
        "result": "MATCH",
    },
]


result = analyze_document_discrepancies(
    subject="RE_ Draft BL INDO SUKSES 65 V.51NW1 PORT KLANG (WESTPORT) - amend BL 055",
    body="Please verify and confirm the draft bill of lading.",
    comparison_rows=comparison_rows,
    status="MISMATCH",
)


print("\nAI DOCUMENT EXPLANATION")
print("=======================")
print(result)