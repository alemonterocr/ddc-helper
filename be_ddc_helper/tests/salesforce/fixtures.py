"""Test fixtures - McElveen Buick GMC questionnaire blob from research.

Source: `Brain/Salesforce Automation Research/Client Questionnaire - Extract
Actual Questionaire.md`. Used as the ground truth for parser tests.
"""

# Tabs are intentional - matches the actual SF Description__c shape.
MCELVEEN_BLOB = (
    "Date Submitted\t\t06/08/26, 12:34 PM\r\n"
    "Dealership Name:\t\tMcElveen Buick GMC\r\n"
    "Dealership Address:\t\t117 Farmington Road, Summerville, SC 29486\r\n"
    "Local Sales Phone #:\t\t+1 (843) 871-6800\r\n"
    "Sales Hours:\t\t9:00am - 8:00pm M-Sa\r\n"
    "Service Department?:\t\tYes\r\n"
    "OEM Dealer Code:\t\tBAC 116456, GMC 53363, Buick 37472\r\n"
    "Inventory Provider:\t\tACV Max\r\n"
    "Leads Email:\t\tMcElveenBuickGMC@newsales.leads.cmdlr.com\r\n"
    "Primary URL/Domain:\t\tmcelveen.com\r\n"
    "Who owns the URL/Domain?\t\tI own the domain\r\n"
    "Current Website Provider:\t\tDealer Inspire\r\n"
    'Design Choice:\t\t{"color":"86","fontFace":"gmc","landingPage":"landing00051","templateHeader":"V9_HEADER_TRUE_MINIMAL_V1","templateHeaderMobile":"V9_HEADER_MOBILE_MINIMAL_V1","templateFooter":"footer-default"}\r\n'
    "Dealership Main Point Of Contact Name:\t\tGray McElveen\r\n"
    "Is this a Buy/Sell\t\tNo\r\n"
    "Do you have access to a Cox Automotive Bridge ID?\t\tYes\r\n"
)

# Synthetic BuySell - matches the wording patterns the user described.
BUYSELL_BLOB_SYNTHETIC = (
    "Date Submitted\t\t06/01/26, 09:00 AM\r\n"
    "Previous Dealership Name:\t\tSmith Chevrolet of Tampa\r\n"
    "New Dealership Name:\t\tBay Area Chevrolet\r\n"
    "Dealership Address:\t\t4242 OCEAN BLVD, TAMPA, FL 33606\r\n"
    "Leads Email:\t\tBayAreaChevy@newsales.leads.cmdlr.com\r\n"
    "Primary URL/Domain:\t\twww.bayareachevy.com\r\n"
    "Design Choice:\t\tWe want something clean and modern, kind of like the current Chevrolet brand site.\r\n"
    "Is this a Buy/Sell\t\tYes\r\n"
)
