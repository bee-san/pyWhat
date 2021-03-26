import click
import regex_identifier

@click.command()
@click.option('-t', '--text', help="The text you want to identify.")
def main(**kwargs):
    print("hello!")
    r = regex_identifier.RegexIdentifier()
    r.check("DANHz6EQVoWyZ9rER56DwTXHWUxfkv9k2o")



main()
