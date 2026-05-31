import { renderToStaticMarkup } from "react-dom/server";
import type { Key } from "react";
import { describe, expect, it } from "vitest";
import { VirtualGrid, resolveVirtualGridTableProps } from "./VirtualGrid";

interface Row {
  id: number;
  name: string;
  score: number;
}

const rows: Row[] = Array.from({ length: 500 }, (_, index) => ({
  id: index,
  name: `row-${index}`,
  score: index,
}));

const columns = [
  {
    dataIndex: "name",
    fixed: "left" as const,
    key: "name",
    sorter: (left: Row, right: Row) => left.name.localeCompare(right.name),
    title: "名称",
  },
  {
    dataIndex: "score",
    filters: [{ text: "高分", value: "high" }],
    key: "score",
    onFilter: (value: boolean | Key, row: Row) => value === "high" && row.score > 400,
    title: "分数",
  },
];

describe("VirtualGrid", () => {
  it("uses the AntD virtual branch with a bounded viewport for 500 rows", () => {
    const tableProps = resolveVirtualGridTableProps<Row>({
      columns,
      dataSource: rows,
      rowKey: "id",
    });

    expect(tableProps.virtual).toBe(true);
    expect(tableProps.scroll).toEqual({ x: 960, y: 420 });
    expect(tableProps.dataSource).toHaveLength(500);
  });

  it("keeps sorting, filtering, and fixed-column table contracts intact", () => {
    const tableProps = resolveVirtualGridTableProps<Row>({
      columns,
      dataSource: rows,
      rowKey: "id",
      scroll: { x: 1280, y: 360 },
    });

    expect(tableProps.columns?.[0]).toMatchObject({ fixed: "left", key: "name" });
    expect(tableProps.columns?.[0]?.sorter).toBe(columns[0].sorter);
    expect(tableProps.columns?.[1]?.filters).toEqual([{ text: "高分", value: "high" }]);
    expect(tableProps.columns?.[1]?.onFilter).toBe(columns[1].onFilter);
    expect(tableProps.scroll).toEqual({ x: 1280, y: 360 });
  });

  it("falls back to the non-virtual branch for expandable or variable-height rows", () => {
    const tableProps = resolveVirtualGridTableProps<Row>({
      columns,
      dataSource: rows,
      expandable: { expandedRowRender: (row) => row.name },
      rowKey: "id",
    });

    expect(tableProps.virtual).toBeUndefined();
    expect(tableProps.scroll).toBeUndefined();
  });

  it("renders through the single grid entrypoint", () => {
    const firstTwoRows = rows.filter((_, index) => index < 2);
    const html = renderToStaticMarkup(
      <VirtualGrid<Row>
        columns={columns}
        dataSource={firstTwoRows}
        rowKey="id"
      />,
    );

    expect(html).toContain("名称");
    expect(html).toContain("row-0");
  });
});
