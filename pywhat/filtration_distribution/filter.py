class Filter:
    @staticmethod
    def filter_by_tag(regexes: dict, filters: set, dont_include: set = set()):
        tags = set(filters["Tags"])

        out = []
        for i in regexes:
            set_tags = set(i["Tags"])
            int = set_tags.intersection(tags)
            print(tags)
            print(int)
            has_tag = bool(int)
            has_no_bad_tags = bool(set_tags.intersection(dont_include))
            if has_tag and has_no_bad_tags:
                out += i
        return out 
