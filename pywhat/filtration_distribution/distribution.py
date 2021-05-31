import json
import os
from pathlib import Path
from typing import Optional

from pywhat.filtration_distribution.filter import Filter


class Distribution:
    """
    A distribution is an object containing the regex
    But the regex has gone through a filter process.

    Example filters:
    * {"Tags": ["Networking"]}
    """

    def __init__(self, filters_dict: Optional[dict] = None):
        # Load the regex
        path = "Data/regex.json"
        fullpath = os.path.join(Path(__file__).resolve().parent.parent, path)
        with open(fullpath, "r") as myfile:
            self.regexes = json.load(myfile)
        
        self.filter_system = Filter()

        # If we are given filters, filter the regex!
        if filters_dict:
            self.filter(filters_dict)
            
        
    def filter(self, filters_dict):
        if "Tags" in filters_dict:
            self.regexes = self.filter_system.filter_by_tag(self.regexes, filters_dict)
    
    def get_regexes(self):
        return self.regexes
        
