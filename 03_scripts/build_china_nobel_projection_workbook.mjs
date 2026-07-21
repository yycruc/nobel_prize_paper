import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = new URL("..", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const outDir = `${decodeURIComponent(root)}02_full_collection/08_report`;
const outPath = `${outDir}/china_nobel_projection_visualization.xlsx`;

const countries = ["China", "France", "Germany", "Japan", "United Kingdom", "United States"];

const awardsLag = [
  ["1901-1910", 1905, 1, 5, 12, 6, 0, 11.5],
  ["1911-1920", 1915, 1, 3, 7, 4, 0, 5.5],
  ["1921-1930", 1925, 2, 7, 9, 3, 0, 8.1],
  ["1931-1940", 1935, 9, 7, 8, 2, 0, 8.4],
  ["1941-1950", 1945, 15, 6, 3, 0, 1, 15.0],
  ["1951-1960", 1955, 28, 9, 3, 0, 0, 13.1],
  ["1961-1970", 1965, 27, 11, 5, 5, 1, 13.4],
  ["1971-1980", 1975, 38, 12, 3, 1, 1, 16.8],
  ["1981-1990", 1985, 36, 4, 9, 1, 2, 18.1],
  ["1991-2000", 1995, 38, 4, 5, 3, 1, 20.8],
  ["2001-2010", 2005, 37, 12, 5, 4, 8, 23.0],
  ["2011-2020", 2015, 33, 14, 4, 5, 8, 26.0],
];

const top21 = [
  ["1850s", 1850, 0.0002, 0.0017, 0.0102, 0.0004, 0.0173, 0.0139],
  ["1860s", 1860, 0.0005, 0.0005, 0.0099, 0.0001, 0.0173, 0.0137],
  ["1870s", 1870, 0.0004, 0.0014, 0.0092, 0.0001, 0.0289, 0.0263],
  ["1880s", 1880, 0.0005, 0.0018, 0.0089, 0.0005, 0.0251, 0.0528],
  ["1890s", 1890, 0.0003, 0.0011, 0.0076, 0.0003, 0.0173, 0.0472],
  ["1900s", 1900, 0.0005, 0.0007, 0.0072, 0.0003, 0.0256, 0.0716],
  ["1910s", 1910, 0.0003, 0.0012, 0.0065, 0.0009, 0.0384, 0.1304],
  ["1920s", 1920, 0.0013, 0.0039, 0.0163, 0.0013, 0.0477, 0.1596],
  ["1930s", 1930, 0.0015, 0.0039, 0.0204, 0.0017, 0.0489, 0.1819],
  ["1940s", 1940, 0.0016, 0.0054, 0.0108, 0.0015, 0.0667, 0.2153],
  ["1950s", 1950, 0.0012, 0.0046, 0.0169, 0.0070, 0.0916, 0.2897],
  ["1960s", 1960, 0.0008, 0.0075, 0.0188, 0.0092, 0.0987, 0.3843],
  ["1970s", 1970, 0.0006, 0.0154, 0.0235, 0.0120, 0.1014, 0.3705],
  ["1980s", 1980, 0.0018, 0.0271, 0.0384, 0.0268, 0.0764, 0.4137],
  ["1990s", 1990, 0.0043, 0.0416, 0.0603, 0.0477, 0.0691, 0.4419],
  ["2000s", 2000, 0.0253, 0.0613, 0.0898, 0.0721, 0.0879, 0.4535],
  ["2010s", 2010, 0.0837, 0.0723, 0.1121, 0.0654, 0.1087, 0.4487],
  ["2020s", 2020, 0.1740, 0.0731, 0.1179, 0.0664, 0.1164, 0.4400],
];

const top77 = [
  ["1850s", 1850, 0.0010, 0.0033, 0.0104, 0.0010, 0.0287, 0.0598],
  ["1860s", 1860, 0.0019, 0.0028, 0.0131, 0.0008, 0.0335, 0.0516],
  ["1870s", 1870, 0.0018, 0.0024, 0.0267, 0.0007, 0.0331, 0.0564],
  ["1880s", 1880, 0.0015, 0.0023, 0.0327, 0.0007, 0.0271, 0.0686],
  ["1890s", 1890, 0.0008, 0.0019, 0.0321, 0.0006, 0.0201, 0.0646],
  ["1900s", 1900, 0.0006, 0.0017, 0.0418, 0.0007, 0.0234, 0.0681],
  ["1910s", 1910, 0.0006, 0.0016, 0.0404, 0.0010, 0.0286, 0.0891],
  ["1920s", 1920, 0.0011, 0.0026, 0.0523, 0.0013, 0.0330, 0.1068],
  ["1930s", 1930, 0.0016, 0.0028, 0.0409, 0.0022, 0.0369, 0.1414],
  ["1940s", 1940, 0.0011, 0.0022, 0.0124, 0.0011, 0.0249, 0.0997],
  ["1950s", 1950, 0.0006, 0.0015, 0.0134, 0.0040, 0.0194, 0.0734],
  ["1960s", 1960, 0.0003, 0.0028, 0.0148, 0.0068, 0.0204, 0.0960],
  ["1970s", 1970, 0.0002, 0.0055, 0.0125, 0.0111, 0.0179, 0.0849],
  ["1980s", 1980, 0.0015, 0.0155, 0.0203, 0.0258, 0.0188, 0.1149],
  ["1990s", 1990, 0.0217, 0.0448, 0.0526, 0.0752, 0.0369, 0.2337],
  ["2000s", 2000, 0.0801, 0.0395, 0.0479, 0.0743, 0.0423, 0.2359],
  ["2010s", 2010, 0.1598, 0.0358, 0.0513, 0.0664, 0.0494, 0.2500],
  ["2020s", 2020, 0.2898, 0.0441, 0.0621, 0.0677, 0.0631, 0.3174],
];

function decadeFromYear(year) {
  return `${Math.floor(year / 10) * 10}s`;
}

function rowByDecade(rows) {
  return Object.fromEntries(rows.map((r) => [r[0], r]));
}

const top21ByDecade = rowByDecade(top21);
const top77ByDecade = rowByDecade(top77);
const countryIndex = {
  China: 2,
  France: 3,
  Germany: 4,
  Japan: 5,
  "United Kingdom": 6,
  "United States": 7,
};

function share(rowsByDecade, decade, country) {
  const row = rowsByDecade[decade];
  return row ? row[countryIndex[country]] : null;
}

const calibration = awardsLag.map((r) => {
  const [awardDecade, awardMid, us, uk, de, fr, jp, lag] = r;
  const sourceYear = awardMid - lag;
  const sourceDecade = decadeFromYear(sourceYear);
  return [
    awardDecade,
    awardMid,
    lag,
    Math.round(sourceYear * 10) / 10,
    sourceDecade,
    us,
    jp,
    share(top21ByDecade, sourceDecade, "United States"),
    share(top21ByDecade, sourceDecade, "Japan"),
    share(top77ByDecade, sourceDecade, "United States"),
    share(top77ByDecade, sourceDecade, "Japan"),
  ];
});

const calibrationLong = [];
for (const row of calibration) {
  calibrationLong.push([row[0], row[4], "United States", row[5], row[7], row[9]]);
  calibrationLong.push([row[0], row[4], "Japan", row[6], row[8], row[10]]);
}

const projection = [
  ["Japan takeoff reference", "1980s", 1985, 0.0268, 0.0258, "2001-2010", 8, "Japan 2000s award rise; publication base roughly 1980s under 23-year lag."],
  ["US early acceleration reference", "1920s", 1925, 0.1596, 0.1068, "1931-1940", 9, "US moved from low awards to visible acceleration."],
  ["US postwar dominance reference", "1940s", 1945, 0.2153, 0.0997, "1951-1960", 28, "US postwar high award output; source decade under lag adjustment."],
  ["China current base", "2010s", 2015, 0.0837, 0.1598, "2030s-2040s", "", "2010s output plus 20-26 year Nobel lag."],
  ["China current base", "2020s", 2025, 0.1740, 0.2898, "2040s-2050s", "", "2020s output plus 20-26 year Nobel lag; decade is incomplete."],
];

function writeTable(sheet, startCell, headers, rows) {
  const start = sheet.getRange(startCell);
  start.write([headers, ...rows]);
}

function styleSheet(sheet) {
  sheet.showGridLines = false;
  const used = sheet.getUsedRange();
  used.format.font = { name: "Microsoft YaHei", size: 10 };
  used.format.wrapText = false;
  used.format.autofitColumns();
}

const workbook = Workbook.create();

const readme = workbook.worksheets.add("README");
readme.getRange("A1").values = [["中国自然科学诺奖时间窗口推导：发文占比、平均时滞与获奖校准"]];
readme.getRange("A3:B12").values = [
  ["核心用途", "用美国、日本历史路径作为可视化参照，观察中国在 Top21/Top77 主要诺奖期刊中的发文占比，经诺奖平均时滞后可能对应的获奖时间窗口。"],
  ["Top21 口径", "发表 8 篇及以上诺奖关键论文的 21 本代表性期刊，更偏核心。"],
  ["Top77 口径", "覆盖约 90% 诺奖关键论文行的扩展代表性期刊，更偏广覆盖。"],
  ["时滞处理", "对每个获奖年代，用该年代自然科学诺奖平均时滞回溯到对应发表年代，再读取美国/日本在该发表年代的期刊发文占比。"],
  ["美国校准", "美国在 1930s 开始明显加速，1950s 后进入高获奖平台期，可作为“大规模领先产出转化为奖项”的参照。"],
  ["日本校准", "日本 2000s 出现自然科学诺奖集中增长，可作为后发国家由论文基础转为奖项的参照。"],
  ["中国判断", "中国 2010s 已明显超过日本起飞前水平，2020s Top21 接近美国早期加速阶段、Top77 超过美国早期参照，但奖项转化通常滞后 20-26 年。"],
  ["谨慎说明", "该模型只能给出时间窗口，不是机械预测。诺奖取决于原创性、学科结构、贡献归属、国际认可与长期验证。"],
  ["建议结论", "中国较可能在 2030s 开始更频繁进入自然科学诺奖候选视野，2040s-2050s 是论文基础充分转化为获奖结果的更关键窗口。"],
  ["图表方法", "Charts 工作表中的图表均基于本工作簿数据；趋势线为 Excel 原生线性趋势线，可右键图表系列调整。"],
];

const awardsSheet = workbook.worksheets.add("Raw_Awards_Lag");
writeTable(
  awardsSheet,
  "A1",
  ["award_decade", "award_mid_year", "United States awards", "United Kingdom awards", "Germany awards", "France awards", "Japan awards", "avg_lag_years"],
  awardsLag,
);

const top21Sheet = workbook.worksheets.add("Raw_Top21");
writeTable(top21Sheet, "A1", ["year_decade", "decade_start", ...countries], top21);

const top77Sheet = workbook.worksheets.add("Raw_Top77");
writeTable(top77Sheet, "A1", ["year_decade", "decade_start", ...countries], top77);

const calSheet = workbook.worksheets.add("Lag_Adjusted_Calibration");
writeTable(
  calSheet,
  "A1",
  ["award_decade", "award_mid_year", "avg_lag_years", "source_year", "source_decade", "US_awards", "Japan_awards", "Top21_US_share", "Top21_Japan_share", "Top77_US_share", "Top77_Japan_share"],
  calibration,
);

const calLongSheet = workbook.worksheets.add("Calibration_Long");
writeTable(calLongSheet, "A1", ["award_decade", "source_decade", "country", "awards", "Top21_share", "Top77_share"], calibrationLong);

const projSheet = workbook.worksheets.add("China_Projection");
writeTable(
  projSheet,
  "A1",
  ["scenario", "source_decade", "source_mid_year", "Top21_share", "Top77_share", "observed_or_projected_award_decade", "awards", "interpretation"],
  projection,
);
projSheet.getRange("J1:N1").values = [["source_decade", "China_Top21", "China_Top77", "base_lag_years", "base_projected_year"]];
projSheet.getRange("J2:N3").values = [
  ["2010s", 0.0837, 0.1598, 23, 2038],
  ["2020s", 0.1740, 0.2898, 26, 2051],
];

const methodSheet = workbook.worksheets.add("Chart_Method");
methodSheet.getRange("A1:B10").values = [
  ["图1 Top21 发文趋势", "用 Raw_Top21 中中国、美国、日本三国按年代的发文占比作折线图，并添加线性趋势线，观察中国是否接近美国早期加速阶段和日本起飞阶段。"],
  ["图2 Top77 发文趋势", "同上，但采用 Top77 扩展口径，观察中国在更广泛代表性诺奖期刊中的整体产出基础。"],
  ["图3 获奖数与平均时滞", "用 Raw_Awards_Lag 中美国、日本获奖数和平均时滞作组合图，说明论文成果到奖项存在显著延迟。"],
  ["图4 Top21 校准散点", "X 轴为按平均时滞回溯后的 Top21 发文占比，Y 轴为后续获奖年代的诺奖数；美国、日本分别为校准样本，并添加线性趋势线。"],
  ["图5 Top77 校准散点", "同图4，但采用 Top77 口径。"],
  ["图6 中国窗口", "把日本起飞、美国早期加速、美国战后高平台与中国 2010s/2020s 位置放在同一表和图中，用 20-26 年时滞给出 2030s-2050s 的窗口。"],
  ["读图原则", "不能把发文占比直接等同于获奖概率。图表只用于说明中国已具备更强的候选成果供给基础，以及这种基础可能在何时进入奖项确认周期。"],
  ["推荐表述", "中国较可能在 2030s 开始更频繁进入自然科学诺奖候选视野；若按 2020s 的产出基础和 20-26 年平均时滞，2040s-2050s 是更关键的获奖转化窗口。"],
  ["注意", "2020s 数据是截至当前的年代均值，后续年份会改变均值。"],
  ["趋势线", "Excel 中右键任一系列 -> 添加趋势线 -> 线性；需要外推时可设置前推/后推，但报告中建议只作定性参考。"],
];

for (const sheet of [readme, awardsSheet, top21Sheet, top77Sheet, calSheet, calLongSheet, projSheet, methodSheet]) {
  styleSheet(sheet);
  const header = sheet.getRange("A1:Z1");
  header.format.fill = "#1F4E79";
  header.format.font = { bold: true, color: "#FFFFFF", name: "Microsoft YaHei", size: 10 };
}

for (const sheet of [top21Sheet, top77Sheet]) {
  sheet.getRange("C2:H19").format.numberFormat = "0.00%";
}
calSheet.getRange("H2:K13").format.numberFormat = "0.00%";
calLongSheet.getRange("E2:F25").format.numberFormat = "0.00%";
projSheet.getRange("D2:E6").format.numberFormat = "0.00%";
projSheet.getRange("K2:L3").format.numberFormat = "0.00%";

await fs.mkdir(outDir, { recursive: true });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outPath);
console.log(outPath);
