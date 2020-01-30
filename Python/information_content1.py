# -*- coding: utf-8 -*-
import re
import traceback
from collections import Counter
from itertools import chain
from math import log

import jieba

STOPWORDS = {
    '孰知', '显然', 'somewhere', 'beforehand', 'better', '确定', '怎', '别', "they're",
    '［①ｃ］', '省得', '慢说', '腾', '还要', "it'd", '密切', '後来', '它们', '们', 'getting',
    '［⑤ｂ］', '岂但', 'four', '一次', '得出', '叮咚', 'happens', '·', '以', '嗡嗡', '虽说',
    '同样', 'less', 'course', '！', '6', "aren't", 'truly', 'allow', '认真', '上去',
    'normally', '哪样', 'new', 'novel', "can't", 'himself', '＝｛', '；', '之', '＋＋',
    'respectively', '上', 'whenever', 'without', "they'd", '那', 'example', '和',
    '及时', 'they', '达到', 'okay', '［④ｅ］', '［②⑩］', '形成', '互相', '纵', '不久', '不能',
    '实际', '个', 'hello', '哪边', 'γ', '掌握', 'definitely', '之一', '其实', '造成', '恰恰相反',
    '小', '处在', 'th', '犹自', '坚持', '_', '哪年', '贼死', 'however', '咋', '正常', '不然',
    '变成', 'clearly', '离', '总之', 'anybody', '这些', "it's", 'zz', '是以', '可', 'her',
    '哟', '复杂', '当然', '/', '呕', '漫说', '宁', '如', '②ｃ', '最后', 'probably', 'whence',
    '［⑧］', '在于', '已经', '结合', '不怕', '虽', '［①Ｅ］', '本地', '继之', '那么样', 'different',
    '比方', '一方面', 'further', '所谓', '㈧ ', '不会', 'unless', '进步', "he's", '那麽', '各',
    '其二', '看见', '而已', '继后', 'we', 'whither', 'meanwhile', '几时', "where's", '冲',
    '欤', '那般', '怎麽', '一些', '安全', '自身', 'amongst', 'gets', '其', '尔尔', 'so', '遇到',
    'were', '合理', 'edu', 'well', '这么点儿', 'following', 'φ', '强调', '一.', 'upon',
    '每年', '那时', '怎奈', 'thank', 'overall', 'also', 'outside', '前面', '开始', '不料',
    '呢', 'may', '为止', '［③ｅ］', '容易', "hadn't", '就要', 'whom', '等等', '呜', '如果',
    'has', 'against', '′∈', 'likely', 'hers', "c'mon", 'myself', '、', 'way',
    '多数', '××× ', '其余', '部分', '些', '看到', '比', 'before', '等到', '［①ｅ］', '若果 ',
    '倘或', 'for', '［①③］', '绝对', '甚么', '只限', '［②', 'particularly', 'old', '哈哈',
    '哗', '这就是说', '％', 'went', '主张', '［①ｏ］', 'my', 'six', 'rd', 'specified',
    'above', '出于', 'need', '哇', '①', '&', '按照', '普遍', 'best', '『', 'available',
    '能否', 'ex', '曾经', '+', '［②ｃ］ ', '总的来看', '能', '［①ｈ］', '［①Ａ］', '如上',
    'provides', '不独', '［②⑧］', '为着', 'appear', '转动', '兼之', '怎么办', '④', '乘',
    'but', '光是', '凡', 'thereafter', '∈［ ', '上来', '9', '一面', 'associated', '较之',
    '乌乎', 'appreciate', '保持', 'could', 'whether', '并且', '只', '当着', '已', '＋',
    '这会儿', 'various', '经', 'etc', 'once', 'wants', '即或', '大批', '出去', '原来', '其他',
    '你们', '来着', '在下', 'keep', 'why', '下列', '适当', '所幸', '［④ｂ］', 'three', 'plus',
    '这点', '构成', '罢了', 'saw', '甚至于', '过来', 'all', '普通', '那个', 'ｃ］', 'non', '赶',
    '矣哉', 'com', 'should', 'these', 'know', 'seeming', 'sent', '完成', 'anyways',
    '［②ｂ］', 'fifth', 'necessary', '丰富', 'kept', '强烈', 'containing', '无法', 'sup',
    '表示', "haven't", '不', '不得', 'indeed', 'regardless', '练习', 'somewhat', '不敢',
    "c's", 'uses', '［①①］', '要不是', '＃', '从', '譬如', '［①ｉ］', '怎么样', 'ｂ］', '［',
    '不特', '过去', '行为', '个别', '仍', '－－ ', '［⑤］', 'un', '除非', '根本', 'with', '由于',
    '你的', '却', '～', '莫不然', '［②Ｇ］', '类如', '因了', '大量', '4', 'get', '如若',
    'regards', 'instead', '又', '准备', '并', '因此', '针对', '仍然', '依靠', '前进', '一般',
    '他', 'Ａ', '等', '? ', '一一', '明显', '据', '朝', '先后', '加强', '以上', '故', '遵循',
    '眨眼', '不过', '及至', 'beside', '其它', '至今', '宁可', '［②ｊ］',
    '…………………………………………………③', '以至于', '真是', '并不是', '有些', 'might', '首先', '=',
    'because', '并没有', '随', '冒', '比如', '末##末', 'soon', '是否', '或者', '毫不', 'near',
    '要么', '〉', '′｜', 'first', '［③⑩］', 'away', '别的', '以至', '同时', '倘使', 'yours',
    '叫做', '相等', '一旦', '介于', '人', 'try', '如上所述', '重大', '同', 'about', '按', '两者',
    'anyway', "t's", '［⑤ａ］', 'hereupon', 'ie', "who's", "there's", '哪些', '纵令',
    '而况', '归', 'thanx', '［①］', '⑤', 'after', '只是', '说说', '并非', 'gone', '比较',
    '立即', 'former', 'nevertheless', '重新', '别说', '任务', '』', '要不然', '至于',
    'thorough', '清楚', "a's", '综上所述', '如何', '若', '特点', 'reasonably', '否则', '着呢',
    '与此同时', '问题', '而后', 'although', '－［＊］－', '就', '～＋', 'which', '借', '有着',
    'maybe', '嗯', 'useful', '认识', 'want', '迅速', '各级', '［②⑥］', 'never', '云云',
    '$', '２．３％', "you'd", 'mean', 'whoever', '以前', 'especially', '照着', '对于',
    'changes', '.一', 'is', 'sensible', '莫如', 'φ．', '⑨', '于是乎', '几', '咧',
    'those', '—', 'greetings', '［①ｄ］', '突出', '庶几', '所以', 'believe', '分别', '吗',
    'whereby', '［③ｄ］', '直接', '正是', '啪达', '重要', '或是', '已矣', 'same', 'third',
    'it', '大', '除此之外', '共同', '之类', '靠', '无', '［②④', 'obviously', '连', '我', '有效',
    '＆', "wouldn't", 'on', '俺们', '不断', '＿', 'willing', '唉', '获得', 'appropriate',
    '吱', 'use', '非常', 'between', '５：０  ', '继而', 'nearly', 'given', '意思', '即若',
    '↑', '多', 'asking', '可见', '０：２ ', 'at', '呵呵', 'cause', '后面', '傥然', '［①Ｄ］',
    "you'll", 'both', 'along', '由此可见', '尚且', 'always', 'came', '［③Ｆ］',
    'actually', "we're", '基本', '有时', 'too', '既是', '为何', '啐', '朝着', '产生', '乃至于',
    '除', '焉', '任', '彼时', '’', '允许', '何', 'to', '下面', '随时', '前此',
    'corresponding', '自从', 'unto', '［③ｈ］', 'two', '以为', 'other', '周围', 'gotten',
    '设或', 'cannot', '看看', 'ａ］', '各地', '认为', 'yes', '正值', '嘿', '〕〔', '啥', '矣',
    'must', 'say', 'another', '～±', "couldn't", '咦', '移动', '与否', '为什麽',
    'behind', '⑥', '但凡', 'themselves', '集中', '于', '则', '像', 'thence', '今年',
    '多么', '鄙人', 'consider', '得', '各人', 'insofar', '此地', '诸', '据此', 'again',
    '固然', "here's", 'still', '使得', '什么', 'much', '上述', '代替', 'mainly', '充分',
    '打', '反过来说', '至', '个人', '－－', 'thats', '尽管如此', '［⑤］］', '［①⑤］', 'et',
    'several', '这边', 'either', '要不', 'you', '［③ｇ］', '把', 'did', 'hence', '伟大',
    '<', 'doing', "let's", '极了', '对比', '该', '遵照', '＜＜', '从事', '随后', '［③ａ］',
    '吧哒', '逐步', '对待', '它', 'seriously', '考虑', 'regarding', 'gives', '巩固', '一个',
    'inasmuch', '无论', '——', '［②Ｂ］ ', '来说', 'immediate', '以後', 'seen', 'serious',
    'any', '因而', '了', 'had', '即便', '反之', '方面', '给', '任何', 'please', '有的是',
    'inc', 'possible', 'selves', 'contain', 'hardly', 'contains', '各自', '用',
    '看出', '-- ', 'later', '况且', 'where', 'across', '最大', '随着', '而言', '宁愿',
    'everything', '果然', 'during', 'until', 'everybody', 'allows', '［④ｄ］', '甚而',
    '［⑥］', 'them', '这种', '｛－', '几乎', '当地', '此间', '可能', '依据', '〕', '加入', '为',
    '是', '采取', '为了', 'their', '不如', '者', 'was', 'indicates', '应用', '应该', '与',
    '大家', ':', '这么', 'comes', '一边', '。', '［⑤ｄ］', '截至', '里面', '始而', '转变', '总是',
    '〔', 'be', '──', '还', 'own', '设使', 'ourselves', 'over', '何况', 'going', '对方',
    '限制', 'anything', '每', '］［', '另外', '有力', '大力', 'vs', '某个', '内', '什么样',
    '［①⑦］', '何以', "hasn't", '失去', '有著', '来自', '唯有', '甚或', '》', 'not', 'hither',
    '［①ｆ］', '［②ｅ］', '一番', '望', 'exactly', '■', '--', '⑦', '其中', '再则', '别人', '本',
    '谁', '被', 'an', '同一', 'followed', 'sure', '即使', 'follows', '般的', '拿',
    '［②③］', '论', '元／吨', '看', 'described', 'alone', 'next', '人们', '……', '何时',
    '俺', '故此', '而', 'very', 'presumably', '某', '《', '就算', '甚且', 'among', '只要',
    '后', "i'd", '扩大', '也就是说', '：', '那边', '数/', '彼', '不足', '［②①］', '表明',
    'latter', '只怕', '比及', '起见', '[', '1', 'else', '云尔', '具体说来', '咳', 'taken',
    'seemed', 'am', "what's", '｝＞', 'now', '③', '坚决', ';', '规定', 'via', 'lest',
    '则甚', '那儿', '最近', '咱', 'eight', "ain't", '之后', '通常', 'me', '非徒', '∪φ∈',
    'does', 'become', '自后', 'throughout', '不外乎', '往往', '不够', '［①Ｂ］', 'ok',
    'unlikely', '总的说来', '後面', '别是', '本着', 'done', '上下', '［③ｃ］', '是不是', "i've",
    '即如', 'this', 'whose', '且', '进入', '良好', '本身', '愿意', 'let', '这么些', 'that',
    '向', '－', "weren't", '所', '而外', '诚如', '另', '他的', '让', '］', 'downwards',
    '避免', '凭借', '二来', '＝″', '自己', '8', '后者', 'Ψ', '哪', '，也 ', '」', 'rather',
    '＝［', 'off', '不若', '啊', '不拘', '为此', 'do', 'tends', '有及', '适应', "you're",
    '呸', 'down', '遭到', '［①Ｃ］', '不论', '然而', 'tried', 'placed', '喔唷', '③］', '相反',
    '／', 'according', 'then', '不是', 'per', '去', '［⑨］ ', '今後', 'your', '严格',
    'aside', 'howbeit', '她', '@', 'secondly', '欢迎', '不可', 'nd', '不惟', '如下',
    'certain', 'theirs', '今', '?', '更加', 'than', '整个', '先生', 'onto', '可以', '存在',
    'come', '沿着', '以及', 'one', '’‘ ', 'ever', '不单', '此外', '【', '不要', '［④ａ］',
    '有点', '＜', 'he', '谁料', '＜±', '那样', '此', 'elsewhere', '正如', '方便', '但是',
    'goes', 'whereas', '［③①］', '［②ａ］', 'someone', '双方', '谁人', '有所', '又及',
    'here', '最好', '才', '既然', '顺着', 'there', 'became', '然后', '相对而言', '而且',
    '）÷（１－', '最', '加以', "you've", '专门', '心里', '行动', '继续', 'value', '上面',
    'particular', '℃ ', '莫若', 'entirely', '第', '://', '企图', '假如', '哪天', '因着',
    'some', '嗡', '也好', 'twice', '所在', '纵然', '甚至', '［⑩］', '#', '某某', './', '还是',
    '可是', '.日 ', '决定', '嘛', '那么', 'viz', '难道说', '突然', '那会儿', '7', '常常', '如其',
    ')', '呵', '另悉', '哩', "we'll", '凭', "they'll", 'help', '怎样', "we've", "'",
    '从而', '及其', '归齐', '怎么', '果真', '［④ｃ］', '不只', '特别是', 'far', '少数', '高兴', '至若',
    '说来', '有关', 'ltd', 'sometimes', '巴', '》），', 'somehow', '？', '出现', '她的',
    '...................', 'are', '具体地说', '不变', '具体', 'our', 'co', '转贴', '趁着',
    '先不先', '取得', '如是', '组成', '要是', 'and', '就是', '-', '哎', '倘然', '咚', 'really',
    '2', 'Ｒ．Ｌ．', 'like', 'relatively', '以故', '为主', '如同', 'can', '就是说', '与其说',
    '将', '使', 'accordingly', 'consequently', '种', '以外', 'known', '［①ｇ］', 'able',
    '竟而', 'under', '下', 'around', '是的', 'his', '着', 'thus', '对应', '前者',
    'second', '设若', '［］', '乎', '犹且', 'five', '说明', '这时', '必须', '起', '一何', '也',
    '明确', 'hereby', '今后', '应当', 'ｆ］', '. ', '帮助', '嗬', '只当', '这样', '不问', '3',
    'she', 'ignored', 'nine', '便于', '引起', '进而', '较', '相对', '哼唷', '相应', 'inner',
    'formerly', '余外', 'causes', 'from', 'considering', '不比', '如此', 'when',
    'wherever', 'none', 'while', '之後', '嘿嘿', 'wish', '管', 'would', '前后', '１． ',
    '结果', 'only', 'often', '进行', '左右', '抑或', 'itself', 'sometime', '旁人', 'take',
    '总结', 'up', 'ｎｇ昉', '惟其', '致', '哪怕', '譬喻', '呜呼', 'what', '注意', '”', '纵使',
    '那么些', 'having', 'hopefully', 'being', '必然', '既往', '即令', '一样', 'Lex ', '的话',
    '大约', '然後', '一下', '任凭', 'currently', 'inward', '严重', '只消', '［⑤ｆ］', '不尽',
    '且不说', '待', '之前', '除外', 'ask', 'therein', 'every', '相同', '赖以', '宁肯', '＞λ',
    '正在', 'moreover', '边', '不尽然', '争取', '适用', '从此', '作为', 'cant', '知道', '来',
    'eg', '此处', '｝', '虽然', '依照', 'zero', 'В', 'except', '非特', '．', '哪儿', '没奈何',
    'been', 'even', '防止', '＋ξ', 'indicated', 'somebody', '喂', '嗳', '］∧′＝［ ',
    '当前', 'right', '［②ｉ］', '）', '吓', 'zt', '这次', '"', 'usually', 'took', 'ours',
    'nowhere', 'tries', '全部', '并不', 'anyone', '跟', '照', '若非', '不仅', '*',
    'seems', '▲', 'us', '为什么', 'toward', '最後', '换句话说', '越是', 'through',
    'thoroughly', '嘎登', '一转眼', '满足', '［③ｂ］', '倘若', 'how', '某些', '嘘', '呃', '别处',
    '基于', '连同', 'no', '［⑤ｅ］', 'otherwise', 'seeing', '第二', 'just', '与其', '每当',
    '积极', '举行', '人家', '［②ｄ］', 'as', "i'll", '一致', "shouldn't", '附近', '再者', '儿',
    'ＬＩ', 'if', '”，', '［④］', 'Ⅲ', 'seem', '战斗', '假使', '（', '一来', '己', '打从',
    'him', "doesn't", '时候', '其一', '这般', '各个', '②', 'out', '相似', '［②ｈ］', '自家',
    '召开', '尽管', 'together', "they've", '，', '哉', '得了', '经常', 'hereafter', '就是了',
    '或', 'looks', '［②⑦］', '再其次', '距', '那里', '得到', '多少', 'oh', '先後', '［②ｆ］',
    'says', '//', '根据', 'nothing', 'tell', '即', '向着', '彼此', 'will', '一片', '此时',
    '或则', '::', '......', 'nobody', 'since', 'already', '何处', '这一来', '以下',
    'theres', '上升', 'perhaps', '而是', ',', '［③］', 'such', '自打', '现在', '尽', '随著',
    '各种', '反映', 'herein', 'yourself', '属于', '亦', '在', 'last', 're', 'shall',
    '广泛', '＝☆', 'ＺＸＦＩＴＬ', '反应', '逐渐', '其次', '无宁', 'got', 'herself', '做到', '＜Δ',
    '么', 'few', '巨大', 'specifying', ']', '诚然', '向使', 'therefore', '他们', '例如',
    '———', '但', '后来', '这里', '】', '.数', '别管', '因为', '不至于', '当时', '要', '中小', '显著',
    '兮', '以便', '往', '诸如', '也是', '这么样', 'in', 'whatever', '那些', '中间', '＊',
    'more', '下来', '替', '通过', 'think', 'sorry', '5', 'go', '既', '喽', '除了', '现代',
    '［＊］', 'liked', '本人', '尔', '这儿', 'thru', 'seven', '不成', 'nor', '需要', '嘎',
    '宣布', '到', '哪里', "it'll", "we'd", '或曰', '［①②］', '仍旧', '然则', 'said', '不一',
    '顺', '乃', '趁', '}', 'many', '巴巴', 'everywhere', '真正', 'towards', '起来', '下去',
    'or', '［①⑧］', '由此', '［①ａ］', '受到', '吧', '的确', '有', 'others', '主要', 'its',
    '所有', '［②⑤］', '由是', 'little', '~~~~', "don't", '一则', 'within', '她们', '另一方面',
    '再说', '呼哧', '必要', '接着', '一切', '>', '若是', '［②②］', 'below', 'welcome', '临',
    'used', '多次', '成为', '＝', '每个', '最高', 'indicate', '彻底', 'almost', 'yet',
    '简言之', "didn't", '运用', '诸位', 'becomes', '→', '(', 'thereupon', '它的', 'name',
    '还有', '＝－', '此次', '乃至', '庶乎', 'quite', 'ought', 'sub', 'whereafter', '好',
    '具有', 'keeps', '一天', '处理', '之所以', '不同', 'hi', '相信', '我们', '对', '有的', '总的来说',
    'looking', '总而言之', '才能', '过', '鉴于', '凡是', 'anyhow', '哈', '0', '‘', "wasn't",
    '依', '自各儿', '这', '及', '只有', 'μ', '十分', 'enough', '阿', '正巧', '由', '－β', '尔后',
    '大大', 'besides', '能够', '以免', '≈ ', '经过', '＜φ', 'exp ', 'lately', 'ZT', '各位',
    '哼', 'least', 'something', 'who', 'whole', 'ｅ］', 'using', '紧接着', '毋宁', '自',
    'afterwards', '以后', '它们的', '目前', '广大', '＇', '一', '特殊', '谁知', '替代', '［②］',
    'furthermore', 'though', '换言之', '有利', '非但', '似乎', '好象', '哎呀', '今天',
    "that's", 'latterly', '这个', 'look', 'wherein', '且说', '觉得', 'apart', '沿',
    'whereupon', 'knows', '哎哟', 'wonder', '不但', '再', '看来', '范围', '许多', 'trying',
    '了解', 'ones', 'see', 'ZZ', 'mostly', '万一', '呀', '［－', '开外', '［①④］', 'of',
    '若夫', '的', '呗', '出来', '没有', '倘', 'anywhere', '虽则', '以致', '于是', '以期',
    'merely', '我的', '再者说', '一时', '好的', '实现', 'despite', '加之', 'thanks', '再有',
    '不管', '每天', '完全', '“', '尤其', '什麽', '咱们', '非独', '）、', '一定', '除开', '你', '哪个',
    'thereby', '相当', '矣乎', '哦', 'yourselves', 'concerning', '联系', '啷当', '一直',
    '曾', '维持', '这麽', 'saying', '反过来', "isn't", 'needs', '⑩', '啦', 'most', '⑧',
    '不妨', '［①⑥］', '当', '以来', '＝（', '似的', '大多数', '开展', 'becoming', '都',
    'certainly', 'que', '很', '因', '地', '［⑦］', 'neither', "won't", '一起', '不光',
    '关于', '他人', '× ', 'beyond', 'have', '１２％', 'Δ', '也罢', 'unfortunately', '假若',
    'namely', 'self', '接著', 'everyone', '自个儿', '深入', '［②ｇ］', 'brief', '全面',
    '＜λ', '...', '直到', 'each', '促进', '您', '要求', 'specify', '用来', '却不', '＞', '叫',
    'into', '使用', 'awfully', 'forth', 'by', '全体', "i'm", 'noone', 'the', '孰料',
    '喏', '故而', '［①⑨］', '×', '反而', 'qv', '嘻'
}  # yapf: disable


__doc__ = '''
前言:
    0. 其实就是模仿信息量(熵)的原理, 分词后, 某个人说的话里面别人不常说的词越多, 信息量越大
    1. 很像 TF-IDF 那套逻辑, 对某个人说的每个词, 在本句话里的频率 / 在全部文本里出现的频率
    2. 目前配合油猴那个 京东评论加载&合并.js 采集某个商品全部评论来过滤
    3. 结果按信息量倒序排列

'''
jieba.setLogLevel(999)
pyperclip = sg = None

# TODO line to remove
import PySimpleGUI as sg


def split_lines(doc):
    if isinstance(doc, str):
        newline_counts = doc.count('\n')
        double_newline_counts = doc.count('\n\n')
        if double_newline_counts > newline_counts / 5:
            # split by double newline
            lines = re.split(r'\n{2,}', doc)
        else:
            lines = doc.split('\n')
        # clean \n
        lines = [line.strip().replace('\n', ' ') for line in lines]
        return lines
    try:
        if not isinstance(doc[0], str):
            raise ValueError
    except (IndexError, ValueError):
        raise IOError(
            'Doc should be string, or list format like ["some string", "string"]'
        )
    return [line.replace('\n', ' ') for line in doc]


def seg_line(line, seg):
    return [i for i in seg(line) if i not in STOPWORDS]


def seg_lines(lines):
    seg = jieba.cut
    all_line_words = []
    for line in lines:
        # print(line)
        words = seg_line(line, seg=seg)
        all_line_words.append(words)
    return all_line_words


def get_info_content(doc, max_freq=None, limit=None, with_score=None):
    result = []
    lines = split_lines(doc)
    all_line_words = seg_lines(lines)
    all_words_c = Counter(chain(*all_line_words))
    if len(all_words_c) < 5:
        return result
    # max_freq = max_freq or (all_words_c.most_common(1)[0][1] / 3)
    total_words_cnt = len(all_words_c)
    for index, words in enumerate(all_line_words):
        if not words:
            continue
        score = 0
        for i in (words):
            all_words_cnt = all_words_c[i]
            # if all_words_cnt < 2:
            word_score = log(total_words_cnt / all_words_cnt)
            score += word_score
        score = score
        # score = math.log(score + 1)
        item = (score, lines[index])
        if item not in result:
            result.append(item)
    result.sort(key=lambda i: i[0], reverse=True)
    if limit:
        if '.' in limit:
            limit = float(limit)
            if limit < 1:
                result = result[:int(len(result) * limit)]
        else:
            result = result[:int(limit)]
    if not with_score:
        result = [i[1] for i in result]
    return result


def get_screensize(zoom=1):
    import ctypes
    user32 = ctypes.windll.user32
    # (2560, 1440)
    screensize = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    return list(int(i * zoom) for i in screensize)


class GUI(object):

    def __init__(self):
        # lazy import
        self.init_import()
        self.init_window()
        self.run()

    def init_window(self):
        button_font = ('mono', 20)
        layouts = [[
            sg.Button('Start', key='start', font=button_font, focus=True),
            sg.Exit(font=button_font),
            sg.Text('Input:', font=button_font),
            sg.Multiline('', key='doc', tooltip='如果留空, 则从剪切板获取'),
            sg.Checkbox('with_score', default=1, key='with_score'),
            sg.Text('Limit:'),
            sg.Input(
                '30', key='limit', size=(5, 1), tooltip='可以是整数, 也可以是小于1的浮点数'),
            sg.Text('', key='bar', size=(10, 1)),
        ], [sg.Output(size=(999, 999), font=('mono', 15), key='output')]]
        half_screen_size = get_screensize(zoom=0.5)
        self.window = sg.Window(
            'Information Content Tool',
            layout=layouts,
            size=half_screen_size,
            resizable=1,
        )

    def init_import(self):
        global pyperclip, sg
        import pyperclip
        import PySimpleGUI as sg

    def run(self):
        e, v = self.window.read(0)
        self.start(v)
        while 1:
            e, v = self.window.read()
            if e in {'Exit', None}:
                break
            elif e == 'start':
                try:
                    self.start(v)
                except Exception:
                    traceback.print_exc()
                continue
        self.window.Close()

    def clear_output(self):
        self.window['output'].Update('')

    def start(self, values):
        self.clear_output()
        doc = values.get('doc', '').strip() or pyperclip.paste()
        kwargs = {'doc': doc}
        for k in ('max_freq', 'limit', 'with_score'):
            kwargs[k] = values.get(k)
        result = get_info_content(**kwargs)
        if kwargs.get('with_score'):
            for score, line in result:
                print(score, line, sep='\t', end='\n\n')
        else:
            for line in result:
                print(line, end='\n\n')
        if result:
            self.window['bar'].Update(f'{len(result)} lines')
        else:
            self.window['bar'].Update('')


def test():
    import pyperclip
    doc = pyperclip.paste()
    for line in get_info_content(doc):
        print(line)

    # 最后再对所有过滤好了的找高频词, 权重按比例降低频率分数
    # 提供几个参数
    # 提供黑名单 白名单 过滤使用
    # 滚动条


if __name__ == "__main__":
    # test()
    GUI()
