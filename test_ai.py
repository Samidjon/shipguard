from ai_service import analyze_shipping_email


result = analyze_shipping_email(
    "Confirm shipping documents",
    """
    Please confirm the shipping instruction and
    bill of lading. Check whether all details match.
    """
)

print(result)