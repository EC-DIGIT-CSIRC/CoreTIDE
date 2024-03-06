from typing import Literal
import os
import git


class Colors:
    PURPLE = "\033[95m"
    DARK_BLUE = "\033[34m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    ORANGE = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    ITALICS = "\033[3m"
    STOP = "\033[0m"
    INVERSE = "\033[7m"


def log(
    category: Literal[
        "ONGOING",
        "SUCCESS",
        "WARNING",
        "INFO",
        "FAILURE",
        "FATAL",
        "DEBUG",
        "SKIP",
        "TITLE",
    ],
    message: str,
    highlight: str = "",
    advice: str = "",
    icon: str = "",
):

    # Escape code sequences for formatting
    PURPLE = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    ORANGE = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    ITALICS = "\033[3m"
    UNDERLINE = "\033[4m"
    STOP = "\033[0m"

    if os.environ.get("TERM_PROGRAM") == "vscode":
        PURPLE = BLUE = CYAN = GREEN = ORANGE = RED = BOLD = ITALICS = UNDERLINE = (
            STOP
        ) = ""

    header = str()

    match category:
        case "ONGOING":
            header = f"⏳ {ORANGE}[ONGOING...]{STOP}"
        case "SUCCESS":
            header = f"✅ {GREEN}[SUCCESS]{STOP}"
        case "WARNING":
            header = f"⚠️ {ORANGE}{BOLD}[WARNING]{STOP}"
        case "INFO":
            header = f"💡 {BLUE}[INFORMATIONAL]{STOP}"
            advice = f"{ITALICS}{advice}{STOP}"
        case "FAILURE":
            header = f"💔 {RED}[FAILURE]{STOP}"
        case "FATAL":
            header = f"☠️ {RED}{UNDERLINE}[FATAL]{STOP}"
            message = f"{RED}{BOLD}{message}{STOP}"
        case "DEBUG":
            header = f"🛠️ {PURPLE}[DEBUG]{STOP}"
            message = f"{BOLD}{message}{STOP}"
        case "SKIP":
            header = f"⏭️ {CYAN}[SKIPPED]{STOP}"
            message = f"{ITALICS}{message}{STOP}"
        case "TITLE":
            header = ""
            padding = "~" * (int((80 - len(message)) / 2))
            message = (
                f"{ORANGE}{padding}{BOLD}{PURPLE}{message}{STOP}{ORANGE}{padding}{STOP}"
            )
            highlight = advice = ""
            str().center
        case _:
            header = ""

    if highlight:
        highlight = f"👉 {PURPLE}{BOLD}{highlight}{STOP}"

    if advice:
        advice = f"💡 {CYAN}{UNDERLINE}{advice}{STOP}"

    message = " " + message + " "
    log_message = str(header) + str(icon) + str(message) + str(highlight) + str(advice)

    if category == "DEBUG":
        if (
            os.environ.get("DEBUG") == True
            or os.environ.get("TERM_PROGRAM") == "vscode"
        ):
            print(log_message)

    elif category != "DEBUG":
        print(log_message)


def coretide_intro():
    BLUE = Colors.DARK_BLUE
    YELLOW = Colors.ORANGE
    STOP = Colors.STOP
    ITALICS = Colors.ITALICS
    BOLD = Colors.BOLD

    coretide = f"{BLUE}Core{YELLOW}TIDE"

    intro = f"""
{BLUE}            :--==-:.       
{BLUE}         -+*###*####*+:      
{BLUE}       -=:   {YELLOW}.:  {BLUE}=-+*##*.              
{BLUE}     -=.  {YELLOW}.:.     {BLUE}.+.*=:+             {STOP}{BOLD}Powered by {coretide}{STOP}
{BLUE}  .-+:  {YELLOW}.-:  :  . {BLUE}-- :  .     
{BLUE}+*#+   {YELLOW}-=.  -:  : {BLUE}:=              {STOP}{ITALICS}The engine powering OpenTIDE Instances{STOP}    
{BLUE}#*-  {YELLOW}.==.  :=  .-  {BLUE}+            {STOP}{ITALICS}Part of the OpenThreat Informed Detection Engineering Initiative{STOP}
{BLUE}:   {YELLOW}:==:   =-  .=. {BLUE}.+      
   {YELLOW}:==-   :=-   --  {BLUE}.+:    {STOP}https://code.europa.eu/ec-digit-s2/opentide/coretide
  {YELLOW}:===.   ==-   :=-   {BLUE}:=-
 {YELLOW}.====    ===.   -=-.    
"""

    return intro
