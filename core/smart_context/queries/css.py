"""Tree-sitter query for CSS - Port từ Repomix queryCss.ts"""

QUERY = """
(comment) @comment

(rule_set
  (selectors) @name.definition.selector
) @definition.selector

(at_rule) @definition.at_rule
"""
