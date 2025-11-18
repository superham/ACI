"""
Prototype sentences for semantic classification in ransomware negotiation chats.

v1 used small dataset of 5 groups to prototype this feature
TODO make large call then modify this to fit additional data
"""

from typing import Dict, List

# based on 24 groups
PROTOTYPES: Dict[str, List[str]] = {
    # KEY DELIVERY & DECRYPTION RELIABILITY
    # Attacker offers to decrypt a few files as proof
    "proof_offer": [
        "you can upload a few encrypted files here for test decryption",
        "send 2-3 random encrypted files and we will decrypt them for free",
        "we can do a test decryption of a small non-critical file",
        "attach several encrypted files and we will return them decrypted",
        "use the trial decryptor to check that decryption works on your sample file",
        "if you need proof, send us some encrypted files for test decryption",
        "before payment you can decrypt any file you want as a test",
        "we will provide a test decryptor so you can verify our decryption",
    ],

    # Victim confirms the sample decryption worked
    "proof_success": [
        "the test files you decrypted opened correctly",
        "the sample file you sent back works",
        "we were able to open the decrypted test files without errors",
        "the decryption tool is working on our test files",
        "the files from the test decryption are readable",
        "the decrypted samples work fine on our side",
    ],

    # Attacker sends or references a decryptor/key (key delivery)
    "key_delivery": [
        "you will receive a universal decryptor for all encrypted files",
        "after payment we will provide the decryption tool",
        "we will send you the decryption key once the transaction is confirmed",
        "here is your decryptor, use it to restore your systems",
        "we will give you a decryptor for each affected system",
        "you can download the decryptor from this link",
        "we will provide an unlocker utility with instructions",
        "we will send you a private key and decryption software",
    ],

    # THREAT FOLLOW-THROUGH (Leaking/Shaming/Auctioning data)
    "leak_threat": [
        "if you do not contact us, we will start publishing your data",
        "if you do not pay, we will publish your data on our leak site",
        "we will upload your stolen data to our blog for everyone to see",
        "your company will appear on our news site with a sample of your files",
        "we will leak your confidential documents to the public",
        "we will post your data on hacker forums and darknet markets",
        "we will gradually publish the files we downloaded from your network",
        "we will publish your clients' data if you keep ignoring us",
        "we will list your company on our data leak page",
        "we will sell or publish your data if you refuse to pay",
    ],

    # Explicit "follow-through" language — attacker says they already leaked
    # or are currently leaking (evidence they tend to act on threats)
    "leak_followthrough": [
        "your data is already published on our leak site",
        "we have already posted your files on our blog",
        "your data has been leaked and is now public",
        "your company is already listed on our data leak site",
        "we have started uploading your data for publication",
        "your databases have already been shared with our partners",
        "your leaks are posted and available for download",
    ],

    # POST-PAYMENT INTEGRITY & RE-EXTORTION
    # Attacker promises deletion / non-disclosure after payment
    "deletion_promise": [
        "after payment we will delete all copies of your data from our servers",
        "we will erase your data from our storage once you pay",
        "we will remove your files from our servers after you send the ransom",
        "we guarantee data deletion after payment is received",
        "your page will be completely deleted from our blog after payment",
        "you will receive a deletion log confirming your data was wiped",
        "we will not keep any backups of your files once the deal is complete",
        "we will delete all stolen data as soon as the transaction is confirmed",
    ],

    # Attacker explicitly promises no future extortion
    "no_future_extortion_promise": [
        "we will not attack you again in the future",
        "you receive a guarantee that our team will never attack you again",
        "after payment this incident is closed and we will forget about you",
        "we will not ask you for more money after this payment",
        "there will be no additional demands once you pay the agreed amount",
        "we will not return to you or target your company again",
    ],

    # Victim accuses attacker of breaking a promise (strong signal)
    "violation_claim": [
        "you promised to delete our data after we paid",
        "you said our data would be deleted from your servers",
        "you said you would not publish our files once we paid",
        "you promised a working decryption key but it does not work",
        "you said you would not attack us again and yet you are back",
        "you are asking for more money after we already paid you",
        "you leaked our data even though we paid the ransom",
    ],

    # Attacker openly engages in re-extortion behavior
    "reextortion_behavior": [
        "you must pay again if you want us to delete the data",
        "the price has increased compared to our first offer",
        "you need to make another payment to extend the deadline",
        "we require additional money to stop the publication of your data",
        "you still have to pay more if you want us to keep our promises",
        "we are making a second demand because you were late with payment",
    ],

    # Attacker states that they sell or reuse data
    # → strong negative for integrity score
    "data_resale_admission": [
        "we will sell your data to interested buyers if you do not pay",
        "your data will be sold on darknet markets",
        "we can sell parts of your data separately or as a whole deal",
        "we sell leaked company data to our partners",
        "we resell corporate data to third parties",
        "your databases will be auctioned if you refuse to negotiate",
        "we trade stolen data and can monetize your information without you",
    ],
}


# Based on 5 groups
# PROTOTYPES: Dict[str, List[str]] = {
#     # KEY DELIVERY & DECRYPTION RELIABILITY
#     # Attacker offers to decrypt a few files as proof
#     "proof_offer": [
#         "send us some encrypted files and we will decrypt them",
#         "we can decrypt test files for you",
#         "we will decrypt a few files as proof",
#         "we will show you we can decrypt your data",
#         "upload several encrypted files for verification",
#         "we will return decrypted samples so you can verify",
#         "we will decrypt sample files to prove we have the key",
#     ],

#     # Victim confirms the sample decryption worked
#     "proof_success": [
#         "the decrypted files work",
#         "the sample you returned is correct",
#         "we can open the decrypted files",
#         "the decryption was successful",
#         "the files you sent back were properly decrypted",
#         "the decrypted samples opened successfully",
#     ],

#     # Attacker sends or references a decryptor/key (key delivery)
#     "key_delivery": [
#         "here is your decryptor",
#         "here is the decryption tool",
#         "we provide the decryptor",
#         "we will send you the key",
#         "here is the key",
#         "download your decryptor here",
#         "you can download the decryption key",
#         "the decryptor is available at this link",
#     ],

#     # THREAT FOLLOW-THROUGH (Leaking/Shaming/Auctioning data)
#     "leak_threat": [
#         "we will publish your data",
#         "your data will be published",
#         "we will leak your files",
#         "your files will be leaked",
#         "we will release your data",
#         "your data will be uploaded",
#         "we will make your data public",
#         "we will put your data on our site",
#         "your company will appear on our news column",
#         "your data will be sold",
#         "we will sell your data",
#         "we will auction your data",
#     ],

#     # Explicit "follow-through" language — attacker says they already leaked
#     # or are currently leaking (evidence they tend to act on threats)
#     "leak_followthrough": [
#         "your data has been published",
#         "your data is already published",
#         "your data has been leaked",
#         "we have released your data",
#         "we already leaked your files",
#         "your files are already on our site",
#         "your data is now public",
#         "your leaks are posted",
#     ],

#     # POST-PAYMENT INTEGRITY & RE-EXTORTION
#     # Attacker promises deletion / non-disclosure after payment
#     "deletion_promise": [
#         "we will delete your data after payment",
#         "we will erase your data",
#         "we will remove your files from our servers",
#         "we guarantee data deletion after you pay",
#         "after payment your data will be deleted",
#         "we will not publish your data once payment is received",
#     ],

#     # Attacker explicitly promises no future extortion
#     "no_future_extortion_promise": [
#         "we will not attack you again",
#         "you will not be targeted again",
#         "we will not ask for more money",
#         "there will be no second demand",
#         "after payment this matter is closed",
#         "we will not return to you again",
#     ],

#     # Victim accuses attacker of breaking a promise (strong signal)
#     "violation_claim": [
#         "you promised to delete our data",
#         "you said the data would be deleted",
#         "you said you would not publish our files",
#         "you said you would not attack us again",
#         "you asked for more money after we paid",
#         "you leaked our data even after payment",
#     ],

#     # Attacker openly engages in re-extortion behavior
#     "reextortion_behavior": [
#         "you must pay again",
#         "the price has increased even after payment",
#         "you need to make another payment",
#         "we require additional money",
#         "you still have to pay more",
#     ],

#     # Attacker states that they sell or reuse data
#     # → strong negative for integrity score
#     "data_resale_admission": [
#         "we sell data",
#         "your data will be sold to third parties",
#         "we resell company data",
#         "we sell leaked data",
#         "we redistribute exfiltrated data",
#     ],
# }
