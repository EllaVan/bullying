你负责修复A3候选输出。invalid_output没有通过validation_error所示的契约校验。

请依据original_request中的current_turn.answer、allowed_units、rules和output_schema，返回一份完整、合法且忠于原回答的新JSON。只输出JSON，不附解释。

要求：
- 不得通过虚构学生原话、槽位、证据或理由来掩盖错误。
- 每个observation完整包含unit_id、status、quote、reference_frame、subject、context_turn_ids、slots、evidence、reason九个字段。
- evidence和slots没有内容时使用[]；reason必须是非空字符串。
- 没有提及的单元直接省略，不得为了覆盖allowed_units而生成记录。
- declined/not_applicable只用于本轮直接追问的target_unit_id；开场回答不得把未提及单元标为not_applicable。
- quote仍须逐字且唯一地来自current_turn.answer。
- 如果没有任何合法观察，返回正确turn_id以及空的observations和background数组。
