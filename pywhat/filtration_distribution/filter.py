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
            has_tag = True if len(int) > 0 else False
            has_no_bad_tags = True if len(set_tags.intersection(dont_include)) == 0 else False
            if has_tag and has_no_bad_tags:
                out += i
        return out 
