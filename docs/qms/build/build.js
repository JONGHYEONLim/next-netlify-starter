const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  Table, TableRow, TableCell, WidthType, BorderStyle, ShadingType,
  Header, Footer, PageNumber, VerticalAlign, LevelFormat, TabStopType, TabStopPosition
} = require('docx');
const fs = require('fs');

// ---------- helpers ----------
const FONT = "맑은 고딕";
const NAVY = "1F3864";
const GREY = "D9D9D9";
const LIGHT = "F2F2F2";

function t(text, opts = {}) {
  return new TextRun({ text, font: FONT, size: opts.size || 20, bold: opts.bold || false, color: opts.color, italics: opts.italics });
}
function p(runs, opts = {}) {
  return new Paragraph({
    children: Array.isArray(runs) ? runs : [runs],
    spacing: { after: opts.after != null ? opts.after : 120, before: opts.before || 0, line: opts.line || 276 },
    alignment: opts.align,
    indent: opts.indent,
  });
}
function h1(num, title) {
  return new Paragraph({
    spacing: { before: 260, after: 120 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: NAVY, space: 4 } },
    children: [ new TextRun({ text: `${num}. ${title}`, font: FONT, size: 24, bold: true, color: NAVY }) ],
  });
}
function body(text, indentLeft = 360) {
  return new Paragraph({
    spacing: { after: 90, line: 276 },
    indent: { left: indentLeft },
    children: [ t(text) ],
  });
}
function sub(label, text, indentLeft = 360) {
  return new Paragraph({
    spacing: { after: 90, line: 276 },
    indent: { left: indentLeft, hanging: 0 },
    children: [ t(label + " ", { bold: true }), t(text) ],
  });
}
function bullet(text) {
  return new Paragraph({
    spacing: { after: 60, line: 276 },
    indent: { left: 720, hanging: 260 },
    children: [ t("· ", { bold: true }), t(text) ],
  });
}
function noBorderCell(children, opts = {}) {
  return new TableCell({
    width: { size: opts.w, type: WidthType.DXA },
    verticalAlign: VerticalAlign.CENTER,
    shading: opts.shading ? { type: ShadingType.CLEAR, fill: opts.shading, color: "auto" } : undefined,
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children,
  });
}

// ---------- document control table (top block) ----------
const titleTable = new Table({
  columnWidths: [6000, 3600],
  width: { size: 9600, type: WidthType.DXA },
  borders: {
    top: { style: BorderStyle.SINGLE, size: 8, color: NAVY },
    bottom: { style: BorderStyle.SINGLE, size: 8, color: NAVY },
    left: { style: BorderStyle.SINGLE, size: 8, color: NAVY },
    right: { style: BorderStyle.SINGLE, size: 8, color: NAVY },
    insideHorizontal: { style: BorderStyle.SINGLE, size: 4, color: NAVY },
    insideVertical: { style: BorderStyle.SINGLE, size: 4, color: NAVY },
  },
  rows: [
    new TableRow({
      children: [
        noBorderCell([
          new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 40 }, children: [ new TextRun({ text: "품질경영시스템 절차서", font: FONT, size: 18, color: "595959" }) ] }),
          new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 40 }, children: [ new TextRun({ text: "부적합품 관리 규정", font: FONT, size: 34, bold: true, color: NAVY }) ] }),
          new Paragraph({ alignment: AlignmentType.CENTER, children: [ new TextRun({ text: "ISO 9001:2015 기반", font: FONT, size: 18, color: "595959" }) ] }),
        ], { w: 6000 }),
        new TableCell({
          width: { size: 3600, type: WidthType.DXA },
          margins: { top: 0, bottom: 0, left: 0, right: 0 },
          children: [
            new Table({
              columnWidths: [1500, 2100],
              width: { size: 3600, type: WidthType.DXA },
              borders: {
                top: { style: BorderStyle.NONE }, bottom: { style: BorderStyle.NONE },
                left: { style: BorderStyle.NONE }, right: { style: BorderStyle.NONE },
                insideHorizontal: { style: BorderStyle.SINGLE, size: 2, color: "BFBFBF" },
                insideVertical: { style: BorderStyle.SINGLE, size: 2, color: "BFBFBF" },
              },
              rows: [
                ["문서번호", "BR-QP-16"],
                ["제 정 일", "2026. 03. 09"],
                ["개정번호", "0"],
                ["개 정 일", "-"],
              ].map(([k, v]) => new TableRow({ children: [
                noBorderCell([ new Paragraph({ children: [ new TextRun({ text: k, font: FONT, size: 16, bold: true, color: NAVY }) ] }) ], { w: 1500, shading: LIGHT }),
                noBorderCell([ new Paragraph({ children: [ new TextRun({ text: v, font: FONT, size: 16 }) ] }) ], { w: 2100 }),
              ]})),
            }),
          ],
        }),
      ],
    }),
  ],
});

// ---------- approval / distribution row ----------
const approvalTable = new Table({
  columnWidths: [1600, 2666, 2667, 2667],
  width: { size: 9600, type: WidthType.DXA },
  borders: {
    top: { style: BorderStyle.SINGLE, size: 4, color: "808080" },
    bottom: { style: BorderStyle.SINGLE, size: 4, color: "808080" },
    left: { style: BorderStyle.SINGLE, size: 4, color: "808080" },
    right: { style: BorderStyle.SINGLE, size: 4, color: "808080" },
    insideHorizontal: { style: BorderStyle.SINGLE, size: 2, color: "808080" },
    insideVertical: { style: BorderStyle.SINGLE, size: 2, color: "808080" },
  },
  rows: [
    new TableRow({ children: [
      noBorderCell([ new Paragraph({ alignment: AlignmentType.CENTER, children: [ new TextRun({ text: "구분", font: FONT, size: 16, bold: true }) ] }) ], { w: 1600, shading: GREY }),
      noBorderCell([ new Paragraph({ alignment: AlignmentType.CENTER, children: [ new TextRun({ text: "작 성", font: FONT, size: 16, bold: true }) ] }) ], { w: 2666, shading: GREY }),
      noBorderCell([ new Paragraph({ alignment: AlignmentType.CENTER, children: [ new TextRun({ text: "검 토", font: FONT, size: 16, bold: true }) ] }) ], { w: 2667, shading: GREY }),
      noBorderCell([ new Paragraph({ alignment: AlignmentType.CENTER, children: [ new TextRun({ text: "승 인", font: FONT, size: 16, bold: true }) ] }) ], { w: 2667, shading: GREY }),
    ]}),
    new TableRow({ children: [
      noBorderCell([ new Paragraph({ alignment: AlignmentType.CENTER, children: [ new TextRun({ text: "직 책", font: FONT, size: 16 }) ] }) ], { w: 1600, shading: LIGHT }),
      noBorderCell([ new Paragraph({ alignment: AlignmentType.CENTER, spacing:{before:60,after:200}, children: [ new TextRun({ text: "품질담당", font: FONT, size: 16 }) ] }) ], { w: 2666 }),
      noBorderCell([ new Paragraph({ alignment: AlignmentType.CENTER, spacing:{before:60,after:200}, children: [ new TextRun({ text: "품질책임자", font: FONT, size: 16 }) ] }) ], { w: 2667 }),
      noBorderCell([ new Paragraph({ alignment: AlignmentType.CENTER, spacing:{before:60,after:200}, children: [ new TextRun({ text: "대표이사", font: FONT, size: 16 }) ] }) ], { w: 2667 }),
    ]}),
  ],
});

// ---------- revision history ----------
function revRow(cells, header = false) {
  const widths = [1000, 4600, 1500, 2500];
  return new TableRow({ children: cells.map((c, i) => noBorderCell([
    new Paragraph({ alignment: i === 1 ? AlignmentType.LEFT : AlignmentType.CENTER, children: [ new TextRun({ text: c, font: FONT, size: 16, bold: header }) ] })
  ], { w: widths[i], shading: header ? GREY : undefined })) });
}
const revTable = new Table({
  columnWidths: [1000, 4600, 1500, 2500],
  width: { size: 9600, type: WidthType.DXA },
  borders: {
    top: { style: BorderStyle.SINGLE, size: 4, color: "808080" },
    bottom: { style: BorderStyle.SINGLE, size: 4, color: "808080" },
    left: { style: BorderStyle.SINGLE, size: 4, color: "808080" },
    right: { style: BorderStyle.SINGLE, size: 4, color: "808080" },
    insideHorizontal: { style: BorderStyle.SINGLE, size: 2, color: "808080" },
    insideVertical: { style: BorderStyle.SINGLE, size: 2, color: "808080" },
  },
  rows: [
    revRow(["개정번호", "개정 조항 및 내용", "개정일", "비고"], true),
    revRow(["0", "제정 (ISO 9001:2015 기반 신규 제정)", "2026.03.09", "신규"]),
    revRow(["", "", "", ""]),
    revRow(["", "", "", ""]),
  ],
});

// ---------- related records ----------
function recRow(cells, header = false) {
  const widths = [4200, 3000, 2400];
  return new TableRow({ children: cells.map((c, i) => noBorderCell([
    new Paragraph({ alignment: i === 0 ? AlignmentType.LEFT : AlignmentType.CENTER, children: [ new TextRun({ text: c, font: FONT, size: 18, bold: header }) ] })
  ], { w: widths[i], shading: header ? GREY : undefined })) });
}
const recTable = new Table({
  columnWidths: [4200, 3000, 2400],
  width: { size: 9600, type: WidthType.DXA },
  borders: {
    top: { style: BorderStyle.SINGLE, size: 4, color: "808080" },
    bottom: { style: BorderStyle.SINGLE, size: 4, color: "808080" },
    left: { style: BorderStyle.SINGLE, size: 4, color: "808080" },
    right: { style: BorderStyle.SINGLE, size: 4, color: "808080" },
    insideHorizontal: { style: BorderStyle.SINGLE, size: 2, color: "808080" },
    insideVertical: { style: BorderStyle.SINGLE, size: 2, color: "808080" },
  },
  rows: [
    recRow(["서식명", "서식번호", "보존기간"], true),
    recRow(["부적합품 보고서", "BR-QF-16-01", "3년"]),
    recRow(["시정조치 요구서", "BR-QF-16-02", "3년"]),
    recRow(["특채(특별채택) 승인서", "BR-QF-16-03", "3년"]),
  ],
});

// ---------- assemble ----------
const children = [
  titleTable,
  new Paragraph({ spacing: { after: 80 }, children: [] }),
  approvalTable,
  new Paragraph({ spacing: { after: 60 }, children: [] }),
  new Paragraph({ alignment: AlignmentType.RIGHT, spacing: { after: 60 }, children: [ new TextRun({ text: "☑ 관리본(CONTROLLED COPY)    ☐ 비관리본(UNCONTROLLED COPY)", font: FONT, size: 16, color: "595959" }) ] }),

  // Revision history
  new Paragraph({ spacing: { before: 120, after: 80 }, children: [ new TextRun({ text: "◈ 개정 이력", font: FONT, size: 20, bold: true, color: NAVY }) ] }),
  revTable,

  // 1. 적용범위
  h1(1, "적용범위"),
  body("본 규정은 braumm(이하 \"당사\")에서 발생하는 부적합한 원·부자재, 반제품(공정품) 및 최종제품에 대한 식별, 격리, 검토, 처리 및 사후관리에 관한 사항을 규정한다."),

  // 2. 목적
  h1(2, "목적"),
  body("규정된 요건에 적합하지 않은 제품이 의도하지 않게 사용되거나 인도(출하)되는 것을 방지하고, 부적합의 재발 요인을 제거함으로써 제품 및 서비스의 품질을 지속적으로 향상시키는 데 그 목적이 있다."),

  // 3. 용어의 정의
  h1(3, "용어의 정의"),
  sub("3.1 부적합품", "규정된 요건에 미달하는 원·부자재부터 최종제품까지의 제품(이하 \"제품\"이라 한다)을 말한다."),
  sub("3.2 시정조치", "발견된 부적합의 원인을 제거하여 재발을 방지하기 위하여 취하는 조치를 말한다."),
  sub("3.3 재작업", "부적합품을 원래의 규정된 요건에 적합하도록 다시 가공·처리하는 행위를 말한다."),
  sub("3.4 수리", "부적합품을 원래의 규정된 요건에는 미치지 못하나 의도된 용도에 사용할 수 있도록 처리하는 행위를 말한다."),
  sub("3.5 특채(특별채택)", "규정된 요건에 적합하지 않으나 권한을 가진 자의 승인을 받아 사용 또는 인도하는 것을 말한다."),
  sub("3.6 폐기", "부적합품을 본래의 용도로 사용할 수 없도록 처리하는 행위를 말한다."),

  // 4. 책임과 권한
  h1(4, "책임과 권한"),
  body("부적합품의 식별, 격리, 문서화된 처리를 위한 평가 및 사후관리에 대한 최종 책임은 대표이사에게 있으며, 실무는 다음과 같이 위임한다."),
  sub("4.1 대표이사", "부적합품의 특채 및 폐기 승인, 시정조치 결과의 최종 확인에 대한 책임과 권한을 가진다."),
  new Paragraph({ spacing: { after: 90, line: 276 }, indent: { left: 360 }, children: [ t("4.2 품질책임자 (품질경영대리인)", { bold: true }) ] }),
  body("4.2.1 부적합품의 검토, 처리방안 결정 및 처리결과 확인에 대한 책임과 권한을 가진다.", 720),
  body("4.2.2 검사(수입·공정·최종) 결과에 따른 부적합품의 식별·격리·문서화 처리를 검토·확인하고, 필요시 관련 부서와 협의한다.", 720),
  body("4.2.3 부적합품 관리업무 전반을 감독하며, 관련 부서 또는 협력업체에 시정조치를 요구하고 그 결과를 확인할 책임과 권한을 가진다.", 720),
  new Paragraph({ spacing: { after: 90, line: 276 }, indent: { left: 360 }, children: [ t("4.3 각 부서장(팀장)", { bold: true }) ] }),
  body("4.3.1 업무 수행 중 발생하는 부적합 자재·공정품·제품을 식별·격리하고 그 사항을 품질책임자 및 대표이사에게 보고하며, 시정조치와 사후관리를 수행할 책임이 있다.", 720),
  body("4.3.2 부적합 현황 및 시정조치 요구서를 접수한 부서장은 조치계획을 수립·해결하고, 부적합품의 식별표시 관리 및 처리결과를 보고한다.", 720),

  // 5. 식별 및 격리
  h1(5, "부적합품의 식별 및 격리"),
  sub("5.1", "부적합품은 적절한 방법으로 식별·표시하여, 처리방안이 결정될 때까지 사용(공정 투입)되거나 인도되지 않도록 한다.", 360),
  sub("5.2", "검사자는 불합격 판정된 자재 또는 제품을 \"부적합(불합격)\" 라벨·태그 또는 별도 지정구역(적색 구역 등)으로 식별하여 후속 공정에 불출되지 않도록 구분·적치한다.", 360),
  sub("5.3", "크기·중량 또는 접근장애 등 물리적 조건으로 격리가 불가능하거나 부적절한 경우에는 \"부적합\" 마킹·태그 등으로 명확히 식별한다.", 360),

  // 6. 문서화
  h1(6, "부적합품의 문서화"),
  sub("6.1", "부적합품이 발생·발견된 경우 해당 부서장은 그 수량과 내용을 「부적합품 보고서(BR-QF-16-01)」 또는 작업일지에 기록한다.", 360),
  sub("6.2", "부적합품의 처리방안은 재작업, 수리, 선별, 특채, 폐기로 구분하며, 상황에 따라 적절한 방법을 선택하여 조치한다.", 360),

  // 7. 업무절차
  h1(7, "업무절차"),
  sub("7.1", "공정 중 발견된 부적합 사항은 처리방안을 마련하기 위하여 관련 기술능력을 보유한 부서에 의해 검토되어야 한다.", 360),
  sub("7.2", "재작업 또는 수리를 실시한 부적합품은 「제품의 모니터링 및 측정 규정」에 따라 반드시 재검사를 실시한다.", 360),
  sub("7.3", "부적합품을 용도 변경할 경우 지정된 보관구역에 식별하여 사용하고, 처리의 적절성을 확인하며, 사용이 불가능한 경우 폐기 또는 반품 조치한다.", 360),
  new Paragraph({ spacing: { after: 60, line: 276 }, indent: { left: 360 }, children: [ t("7.4 부적합의 종류", { bold: true }) ] }),
  bullet("고객 불만사항(CLAIM)"),
  bullet("내부심사 및 경영검토 시 지적되는 부적합 사항"),
  bullet("수입검사·공정검사·최종검사에서 발견되는 부적합품"),
  sub("7.5 고객 불만사항(CLAIM)", "고객 불만의 접수 및 처리는 「고객 만족 및 의사소통 규정」에 따라 처리한다.", 360),
  sub("7.6 수입·최종검사 시 부적합품", "검사 담당자가 6.1항에 따라 작성·기록하고 품질책임자에게 통보한다.", 360),
  new Paragraph({ spacing: { after: 90, line: 276 }, indent: { left: 360 }, children: [ t("7.7 공정 중 발생하는 부적합품", { bold: true }) ] }),
  body("7.7.1 부적합품의 기준: 각 공정의 부적합 기준은 QC공정도, 검사기준서 및 작업표준서에 따른다.", 720),
  body("7.7.2 부적합 발생 시 조치: 공정 담당자 또는 검사원은 부적합품 발견 시 해당 작업을 중지하고 부서장에게 보고하며, 24시간 이내에 조치한다.", 720),
  body("7.7.3 수리 불가능한 공정 부적합품 및 장기 보관으로 인한 부적합품은 매월 별도 기안하여 대표이사의 승인을 받아 폐기 처리한다.", 720),
  new Paragraph({ spacing: { after: 90, line: 276 }, indent: { left: 360 }, children: [ t("7.8 특채(특별채택)", { bold: true }) ] }),
  body("규정된 요건에 미달하나 사용이 가능하다고 판단되는 경우, 「특채 승인서(BR-QF-16-03)」를 작성하여 대표이사(또는 고객)의 승인을 받은 후 사용 또는 인도할 수 있다.", 720),
  new Paragraph({ spacing: { after: 90, line: 276 }, indent: { left: 360 }, children: [ t("7.9 시정조치", { bold: true }) ] }),
  body("반복적·중대한 부적합에 대해서는 「시정조치 요구서(BR-QF-16-02)」를 발행하여 원인 분석 및 재발방지 대책을 수립하고, 그 유효성을 확인한다.", 720),

  // 8. 관련기록
  h1(8, "관련기록"),
  recTable,
];

const doc = new Document({
  creator: "braumm",
  title: "부적합품 관리 규정 (BR-QP-16)",
  description: "braumm Quality Management System Procedure - Control of Nonconforming Product",
  styles: { default: { document: { run: { font: FONT, size: 20 } } } },
  sections: [{
    properties: { page: { margin: { top: 1100, bottom: 1100, left: 1100, right: 1100 } } },
    headers: {
      default: new Header({ children: [ new Paragraph({
        tabStops: [{ type: TabStopType.RIGHT, position: 9600 }],
        border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: "BFBFBF", space: 2 } },
        children: [
          new TextRun({ text: "braumm", font: FONT, size: 18, bold: true, color: NAVY }),
          new TextRun({ text: "\t부적합품 관리 규정", font: FONT, size: 16, color: "595959" }),
        ],
      }) ] }),
    },
    footers: {
      default: new Footer({ children: [ new Paragraph({
        alignment: AlignmentType.CENTER,
        border: { top: { style: BorderStyle.SINGLE, size: 4, color: "BFBFBF", space: 2 } },
        children: [
          new TextRun({ text: "문서번호: BR-QP-16    |    ", font: FONT, size: 15, color: "808080" }),
          new TextRun({ children: ["Page ", PageNumber.CURRENT, " / ", PageNumber.TOTAL_PAGES], font: FONT, size: 15, color: "808080" }),
          new TextRun({ text: "    |    본 문서는 braumm의 자산이며 무단 복제·배포를 금함", font: FONT, size: 15, color: "808080" }),
        ],
      }) ] }),
    },
    children,
  }],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync("부적합품_관리_규정_BR-QP-16.docx", buf);
  console.log("written", buf.length);
});
