import click
import identifier

@click.command()
# @click.option('-t', '--text', help="The text you want to identify.", required=True)
@click.argument('text_input', required=True)
def main(text_input):
    """
    What - Identify what something is.\n
    Made by Bee https://twitter.com/bee_sec_san
    https://github.com/bee-san\n

    Examples:

        * what "HTB{this is a flag}"

        * what "0x52908400098527886E0F7030069857D2E4169EE7"
        

    """
    r = regex_identifier.RegexIdentifier()
    print("This is a " + r.check(text_input)[0]["Name"])

class What:
    def __init__(self):
        self.id = identifier

def what_is_this(text: str) -> dict:


if __name__ == "__main__":
    main()