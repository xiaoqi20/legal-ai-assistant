export interface AnswerSpan {
  text: string;
  bold?: boolean;
  num?: boolean;
}

export interface AnswerBlock {
  lines: AnswerSpan[][];
  heading?: boolean;
  indent?: boolean;
  right?: boolean;
  blue?: boolean;
}

const span = (text: string): AnswerSpan => ({ text });
const bold = (text: string): AnswerSpan => ({ text, bold: true });
const number = (value: number): AnswerSpan => ({
  text: `${value}.`,
  bold: true,
  num: true,
});
const paragraph = (...content: AnswerSpan[]): AnswerBlock => ({
  lines: [content],
});
const heading = (text: string): AnswerBlock => ({
  lines: [[span(text)]],
  heading: true,
});
const indented = (text: string): AnswerBlock => ({
  lines: [[span(text)]],
  indent: true,
});
const blue = (...content: AnswerSpan[]): AnswerBlock => ({
  lines: [content],
  blue: true,
});
const multiline = (lines: string[]): AnswerBlock => ({
  lines: lines.map((line) => [span(line)]),
});
const right = (lines: string[]): AnswerBlock => ({
  lines: lines.map((line) => [span(line)]),
  right: true,
});

const tort: AnswerBlock[] = [
  paragraph(
    span("根据案件信息，被告李某强行进入房屋并更换门锁的行为可能构成侵权。以下是分析："),
  ),
  paragraph(
    number(1),
    span(" "),
    bold("房屋买卖合同的履行："),
    span(
      "原告张某已支付全部购房款项并完成过户手续，依法享有对房产的占有权。",
    ),
  ),
  paragraph(
    number(2),
    span(" "),
    bold("被告行为的性质："),
    span(
      "李某未经同意进入房屋并更换门锁，妨碍了张某对房产的正常使用，侵犯了原告的合法权益。",
    ),
  ),
  paragraph(
    number(3),
    span(" "),
    bold("侵权责任："),
    span(
      "根据《中华人民共和国民法典》，未经允许侵入他人财产并妨碍其使用的行为构成侵权，侵权人应承担相应责任。",
    ),
  ),
  paragraph(
    span(
      "因此，被告李某的行为构成侵权，应承担停止侵权、恢复原状及赔偿损失的责任。建议原告继续提供相关证据支持其经济损失的主张。",
    ),
  ),
];

const defense: AnswerBlock[] = [
  heading("【案情分析】"),
  paragraph(
    span(
      "民事答辩状是被告在民事诉讼中针对原告的起诉状内容进行回应的法律文书。其主要目的是对原告提出的诉讼请求、事实和理由进行反驳或辩解，以维护被告的合法权益。答辩状应当包括被告的基本信息、对原告起诉状的回应、被告的主张和理由、以及相关的证据材料。",
    ),
  ),
  heading("【结果分析】"),
  paragraph(
    number(1),
    span(" "),
    span(
      "答辩状的提交是民事诉讼程序中的重要环节，它直接影响法院对案件的审理和判决。如果被告能够提供充分的证据和合理的辩解，可能会改变法院对案件的初步看法，甚至影响最终的判决结果。",
    ),
  ),
  paragraph(number(2), span(" "), span("行动建议")),
  paragraph(
    number(3),
    span(" "),
    span(
      "准备答辩状：根据原告的起诉状内容，详细准备答辩状，明确回应原告的每一项诉讼请求和理由。",
    ),
  ),
  paragraph(
    number(4),
    span(" "),
    span(
      "收集证据：收集能够支持被告主张的证据材料，如合同、协议、通信记录、证人证言等。",
    ),
  ),
  paragraph(
    span(
      "法律咨询：在准备答辩状的过程中，建议咨询专业律师，确保答辩状的法律依据充分且合理。",
    ),
  ),
  paragraph(
    span(
      "按时提交：按照法院规定的时间提交答辩状，避免因逾期提交而影响诉讼权利。",
    ),
  ),
];

const caseSort: AnswerBlock[] = [
  paragraph(bold("案件名称："), span("房屋买卖合同纠纷案")),
  paragraph(bold("案件类型："), span("民事案件")),
  paragraph(bold("当前案件状态："), span("一审")),
  paragraph(bold("委托人的诉讼地位："), span("原告")),
  paragraph(bold("委托人的名称："), span("张委托")),
  paragraph(bold("当事人信息：")),
  paragraph(span("原告：张某")),
  paragraph(span("被告：李某")),
  paragraph(bold("案件背景：")),
  paragraph(
    span(
      "原告张某与被告李某于2020年1月1日签订了一份房屋买卖合同，约定被告将位于某市某区某路某号的一套房产以人民币100万元的价格出售给原告。原告按照合同约定支付了全部购房款项，并完成了房屋过户手续。然而，2020年5月，被告李某以房产价值低估为由，要求原告额外支付人民币20万元，否则将收回房产。原告拒绝了被告的要求。随后，被告李某强行进入房屋并更换了门锁，导致原告无法正常使用房屋。",
    ),
  ),
  paragraph(bold("争议焦点：")),
  paragraph(span("一、原告：合同效力及履行")),
  paragraph(span("二、被告：合同条款理解及款项到账情况")),
  paragraph(bold("证据分析：")),
  paragraph(
    span(
      "原告方证据链较为完整，能够证明合同签订、房款支付及过户事实；被告方证据不足以支持其抗辩主张。",
    ),
  ),
];

const evidenceSort: AnswerBlock[] = [
  paragraph(span("在本案中，证据清单可以梳理如下：")),
  blue(bold("原告张某提供的证据：")),
  paragraph(number(1), span(" "), span("房屋买卖合同原件：")),
  indented("证明目的：证明合同的有效性及履行情况。"),
  paragraph(number(2), span(" "), span("银行转账记录：")),
  indented("证明目的：证明已支付全部购房款项。"),
  paragraph(number(3), span(" "), span("房产证复印件：")),
  indented("证明目的：证明已完成房屋过户手续。"),
  paragraph(number(4), span(" "), span("物业证明：")),
  indented("证明目的：证明被告李某侵权行为（强行进入房屋并更换门锁）。"),
  blue(bold("被告李某提供的证据：")),
  paragraph(number(1), span(" "), span("房屋买卖合同原件：")),
  indented("证明目的：证明合同条款的理解。"),
  paragraph(number(2), span(" "), span("银行转账记录：")),
  indented("证明目的：核实款项到账情况。"),
  blue(bold("证据分析：")),
  paragraph(
    span(
      "原告提供的证据能够形成完整证据链，被告提供的证据不足以反驳原告主张，建议原告补充物业出具的侵权事实证明。",
    ),
  ),
];

const generic: AnswerBlock[] = [
  paragraph(span("您好，我是小诺。根据您的问题，我先给出以下初步分析：")),
  paragraph(
    number(1),
    span(" "),
    bold("法律关系判断："),
    span("需要结合合同约定、履行情况以及双方沟通记录综合判断各方权利义务。"),
  ),
  paragraph(
    number(2),
    span(" "),
    bold("证据准备："),
    span("建议优先收集合同原件、付款凭证、聊天记录等能够证明基础事实的材料。"),
  ),
  paragraph(
    number(3),
    span(" "),
    bold("行动建议："),
    span("可以先通过书面函件固定对方违约事实，再根据情况选择协商、调解或诉讼途径。"),
  ),
  paragraph(span("以上内容仅供参考，具体方案建议结合完整案件材料进一步分析。")),
];

const lawsuit: AnswerBlock[] = [
  heading("【民事起诉状（草稿）】"),
  paragraph(bold("原告："), span("张某，男，汉族，住某市某区某路某号。")),
  paragraph(bold("被告："), span("李某，男，汉族，住某市某区某路某号。")),
  paragraph(bold("诉讼请求：")),
  paragraph(number(1), span(" "), span("判令被告停止侵权，恢复房屋原状；")),
  paragraph(
    number(2),
    span(" "),
    span("判令被告赔偿原告经济损失人民币20,000元；"),
  ),
  paragraph(number(3), span(" "), span("本案诉讼费用由被告承担。")),
  paragraph(bold("事实与理由：")),
  paragraph(
    span(
      "原告与被告于2020年1月1日签订房屋买卖合同，原告已支付全部购房款并完成过户。2020年5月，被告以房产价值低估为由要求额外支付20万元，遭拒后强行进入房屋并更换门锁，导致原告无法正常使用房屋。",
    ),
  ),
  paragraph(
    span(
      "被告的行为已构成侵权，依据《中华人民共和国民法典》相关规定，应承担停止侵害、恢复原状及赔偿损失的责任。",
    ),
  ),
  multiline(["此致", "某市某区人民法院"]),
  right(["具状人：张某", "2024年10月15日"]),
];

const debt: AnswerBlock[] = [
  paragraph(span("别人欠钱逾期未还，可以按以下步骤处理：")),
  paragraph(
    number(1),
    span(" "),
    bold("固定证据："),
    span("保存借条、转账记录、微信聊天记录、催款记录等。"),
  ),
  paragraph(
    number(2),
    span(" "),
    bold("发送催告："),
    span("通过短信、微信或律师函方式书面催告，明确还款期限。"),
  ),
  paragraph(
    number(3),
    span(" "),
    bold("诉讼准备："),
    span("确认被告身份信息及管辖法院，准备起诉状和证据清单。"),
  ),
  paragraph(
    number(4),
    span(" "),
    bold("注意时效："),
    span("普通诉讼时效为三年，及时主张权利并保留催告证据。"),
  ),
  paragraph(span("如金额较大或对方失联，建议尽早咨询专业律师。")),
];

const evidenceCollect: AnswerBlock[] = [
  paragraph(span("快速收集案件证据可以从以下几个方面入手：")),
  paragraph(
    number(1),
    span(" "),
    bold("书面材料："),
    span("合同、协议、发票、收据、函件等原件或清晰扫描件。"),
  ),
  paragraph(
    number(2),
    span(" "),
    bold("电子数据："),
    span("微信/短信聊天记录、邮件、转账记录、通话录音，注意保留原始载体。"),
  ),
  paragraph(
    number(3),
    span(" "),
    bold("音视频资料："),
    span("现场照片、监控录像、录音，记录拍摄时间、地点和拍摄人。"),
  ),
  paragraph(
    number(4),
    span(" "),
    bold("证人证言："),
    span("提前沟通证人，必要时申请证人出庭。"),
  ),
  paragraph(
    span("收集时注意合法性和完整性，避免剪辑或篡改，并制作证据清单。"),
  ),
];

export function getMockAnswer(question: string): AnswerBlock[] {
  const text = question.toLowerCase();
  if (text.includes("答辩")) return defense;
  if (text.includes("侵权")) return tort;
  if (text.includes("证据清单")) return evidenceSort;
  if (text.includes("案情梳理") || text.includes("案件梳理")) return caseSort;
  if (text.includes("起诉")) return lawsuit;
  if (text.includes("欠") || text.includes("逾期")) return debt;
  if (text.includes("收集") || text.includes("证据")) return evidenceCollect;
  return generic;
}

export function answerToPlainText(blocks: AnswerBlock[]): string {
  return blocks
    .map((block) =>
      block.lines
        .map((line) => line.map((span) => span.text).join(""))
        .join("\n"),
    )
    .join("\n\n");
}
