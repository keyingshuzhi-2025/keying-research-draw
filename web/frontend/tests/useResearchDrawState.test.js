import { describe, expect, it } from "vitest";

import { useResearchDrawState } from "../src/composables/useResearchDrawState";

describe("useResearchDrawState", () => {
  it("uses expected default state", () => {
    const state = useResearchDrawState();
    expect(state.selectedGroup.value).toBe("stats_2d");
    expect(state.selectedPlot.value).toBe("box");
    expect(state.renderMode.value).toBe("file");
    expect(state.fmt.value).toBe("png");
    expect(state.sectionDefs).toHaveLength(4);
  });

  it("derives required fields from registry metadata", () => {
    const state = useResearchDrawState();
    state.selectedPlot.value = "scatter";
    state.plotRegistry.value = {
      scatter: {
        required_fields: ["x_col", "y_col"]
      }
    };
    expect(state.requiredFields.value).toEqual(["x_col", "y_col"]);
    expect(state.missingRequiredFields.value).toEqual(["x_col", "y_col"]);

    state.mappings.x_col = "x";
    expect(state.missingRequiredFields.value).toEqual(["y_col"]);
  });

  it("uses Chinese chart labels and keeps the about catalog demo-ready", () => {
    const state = useResearchDrawState();
    state.plotsByGroup.value = { stats_2d: ["bar", "column"] };
    state.plotRegistry.value = {
      bar: { display_name: "横向条形图", description: "按类别横向比较数值。" },
      column: { display_name: "纵向柱状图", description: "按类别纵向比较数值。" }
    };

    expect(state.plotDisplayName("column")).toBe("纵向柱状图");
    expect(state.plotDisplayName("line")).toBe("折线图");
    expect(state.aboutPlotCatalog.value[0].plots).toEqual([
      { key: "bar", label: "横向条形图", description: "按类别横向比较数值。" },
      { key: "column", label: "纵向柱状图", description: "按类别纵向比较数值。" }
    ]);
    expect(state.aboutOverview.value.find((item) => item.label === "内置演示").value).toBe("2 种");
  });
});
