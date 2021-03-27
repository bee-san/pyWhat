import click
import regex_identifier

@click.command()
@click.option('-t', '--text', help="The text you want to identify.", required=True)
def main(**kwargs):
    r = regex_identifier.RegexIdentifier()
    print("This is a " + r.check(kwargs["text"])[0]["Name"])

if __name__ == "__main__":
    main()