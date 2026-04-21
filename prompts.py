# prompts.py
# 存放 LLM 提示词模板与关键词库

# ====================== LLM 系统提示词 ======================
SYSTEM_PROMPT_TEMPLATE = """你是跨境电商AI客服转人工质检专家，严格按以下10类分类。
1.商品信息不足 2.修改订单信息 3.店铺政策要求 4.客户要求 5.售后退款退货 6.物流（含错发漏发） 7.定制服务 8.商品质量问题（仅破损瑕疵等） 9.AI关闭直接转人工 10.未知
优先级：售后退款退货>物流>商品质量问题>修改订单信息>定制服务>商品信息不足>客户要求>店铺政策要求>AI关闭直接转人工>未知
输出JSON：{{"转人工类别": "类别名", "核心触发问题": "简短描述"}}
对话内容：
{compact_session}"""

# ====================== 增强版系统提示词 ======================
ENHANCED_SYSTEM_PROMPT_TEMPLATE = """你是跨境电商AI客服转人工质检专家，严格按以下10类分类。
1.商品信息不足 2.修改订单信息 3.店铺政策要求 4.客户要求 5.售后退款退货 6.物流（含错发漏发） 7.定制服务 8.商品质量问题（仅破损瑕疵等） 9.AI关闭直接转人工 10.未知

分类规则：
- 售后退款退货：客户明确提到退款、退货、换货、补发、理赔、售后等关键词
- 物流：客户提到快递、派送、丢件、延误、没收到、错发、漏发、发错、发漏等
- 商品质量问题：客户提到破损、瑕疵、故障、不符、质量问题、坏了、脏了等
- 修改订单信息：客户提到改地址、改单、修改订单、合并订单等
- 定制服务：客户提到定制、个性化、印字、印号、团队名等
- 商品信息不足：客户提到参数、库存、规格、材质、尺寸、尺码等
- 客户要求：客户明确要求转人工、找人工、有人吗等
- 店铺政策要求：系统提示无售后、after-sales等
- AI关闭直接转人工：AI关闭且无AI消息
- 未知：无法确定具体类别

优先级：售后退款退货>物流>商品质量问题>修改订单信息>定制服务>商品信息不足>客户要求>店铺政策要求>AI关闭直接转人工>未知

输出JSON：{{"转人工类别": "类别名", "核心触发问题": "简短描述", "置信度": "高/中/低"}}
对话内容：
{compact_session}"""

# ====================== 简化版系统提示词 ======================
SIMPLE_SYSTEM_PROMPT_TEMPLATE = """你是跨境电商AI客服转人工质检专家，按以下10类分类：
1.商品信息不足 2.修改订单信息 3.店铺政策要求 4.客户要求 5.售后退款退货 6.物流 7.定制服务 8.商品质量问题 9.AI关闭直接转人工 10.未知

输出JSON：{{"转人工类别": "类别名"}}
对话内容：
{compact_session}"""

# ====================== 关键词库（错发漏发归入物流） ======================
KEYWORDS = {
    "客户要求": {
        "zh": ["人工", "转人工", "客服", "找人工", "有人吗"],
        "en": ["agent", "human", "talk to representative"],
        "tl": ["kausapin ang tao", "agent", "customer service"],
    },
    "售后退款退货": {
        "zh": ["退款", "退货", "换货", "补发", "理赔", "售后"],
        "en": ["refund", "return", "exchange", "compensation"],
        "tl": ["refund", "ibalik", "palitan", "kompensasyon"],
    },
    "商品质量问题": {
        "zh": ["破损", "瑕疵", "故障", "不符", "质量问题", "坏了", "脏了"],
        "en": ["damaged", "defective", "quality issue", "broken"],
        "tl": ["sira", "may depekto", "pangit", "nipis", "hindi maganda"],
    },
    "物流": {
        "zh": ["物流", "快递", "派送", "丢件", "延误", "没收到", "错发", "漏发", "发错", "发漏"],
        "en": ["logistics", "delivery", "shipping", "tracking", "not received", "wrong item", "missing item"],
        "tl": ["delivery", "shipping", "kailan darating", "parcel", "hindi pa natatanggap", "maling item", "kulang", "mali ang naipadala"],
    },
    "修改订单信息": {
        "zh": ["改地址", "改单", "修改订单", "合并订单"],
        "en": ["change address", "modify order"],
        "tl": ["palitan ang address", "baguhin ang order"],
    },
    "定制服务": {
        "zh": ["定制", "个性化", "印字", "印号", "团队名"],
        "en": ["custom", "print name", "number", "team name"],
        "tl": ["pangalan", "numero", "team name", "ipaprint", "custom", "magpa-customize", "pasadya"],
    },
    "商品信息不足": {
        "zh": ["参数", "库存", "规格", "材质", "尺寸", "尺码"],
        "en": ["size", "material", "stock", "specification"],
        "tl": ["sukat", "size", "materyales", "stock"],
    },
}