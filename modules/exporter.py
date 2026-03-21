import os
import json
from pathlib import Path
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

DATA_DIR = "articles_data"

class ExcelExporter:
    def __init__(self, data_dir: str = DATA_DIR):
        self.data_dir = Path(data_dir)
    
    def export_account(self, account_name: str, output_file: str = None) -> str:
        json_file = self.data_dir / f"{account_name}_list.json"
        
        if not json_file.exists():
            print(f"[❌] 未找到JSON文件: {json_file}")
            return None
        
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        articles = data.get('articles', [])
        
        if not articles:
            print(f"[❌] 没有文章数据")
            return None
        
        if not output_file:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f"{account_name}_{timestamp}.xlsx"
        
        wb = Workbook()
        ws = wb.active
        ws.title = "文章列表"
        
        headers = ['序号', '公众号名称', '文章标题', '文章链接', '发布日期', '阅读量', '标签', '是否原创', '下载状态', '备注']
        
        header_font = Font(bold=True, color='FFFFFF', size=11)
        header_fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
        header_alignment = Alignment(horizontal='center', vertical='center')
        
        thin_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment
            cell.border = thin_border
        
        for row, article in enumerate(articles, 2):
            ws.cell(row=row, column=1, value=article.get('seq', row-1))
            ws.cell(row=row, column=2, value=account_name)
            ws.cell(row=row, column=3, value=article.get('title', ''))
            ws.cell(row=row, column=4, value=article.get('url', ''))
            ws.cell(row=row, column=5, value=article.get('publish_date', ''))
            
            read_count = article.get('read_count', 0)
            if read_count:
                ws.cell(row=row, column=6, value=read_count)
            
            tags = article.get('tags', [])
            ws.cell(row=row, column=7, value=', '.join(tags) if tags else '')
            
            ws.cell(row=row, column=8, value='是' if article.get('is_original') else '否')
            
            downloaded = article.get('downloaded', False)
            ws.cell(row=row, column=9, value='已下载' if downloaded else '未下载')
            
            remark = article.get('remark', '')
            ws.cell(row=row, column=10, value=remark)
            
            for col in range(1, len(headers) + 1):
                cell = ws.cell(row=row, column=col)
                cell.border = thin_border
                if col == 3:
                    cell.alignment = Alignment(wrap_text=True)
                elif col in [4, 7]:
                    cell.alignment = Alignment(wrap_text=True)
        
        column_widths = {
            1: 8,
            2: 20,
            3: 50,
            4: 60,
            5: 20,
            6: 12,
            7: 25,
            8: 10,
            9: 12,
            10: 25
        }
        
        for col, width in column_widths.items():
            ws.column_dimensions[get_column_letter(col)].width = width
        
        ws.row_dimensions[1].height = 25
        
        ws.freeze_panes = 'A2'
        
        try:
            wb.save(output_file)
            print(f"[✅] Excel文件已导出: {output_file}")
            return output_file
        except Exception as e:
            print(f"[❌] 导出失败: {e}")
            return None
    
    def export_all(self, output_dir: str = '.') -> list:
        output_dir = Path(output_dir)
        output_dir.mkdir(exist_ok=True)
        
        exported_files = []
        
        for json_file in self.data_dir.glob('*_list.json'):
            account_name = json_file.stem.replace('_list', '')
            output_file = output_dir / f"{account_name}.xlsx"
            
            result = self.export_account(account_name, str(output_file))
            if result:
                exported_files.append(result)
        
        return exported_files
    
    def export_summary(self, output_file: str = 'articles_summary.xlsx') -> str:
        wb = Workbook()
        ws = wb.active
        ws.title = "汇总"
        
        headers = ['公众号名称', '文章总数', '已下载', '未下载', '采集时间']
        
        header_font = Font(bold=True, color='FFFFFF', size=11)
        header_fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
        header_alignment = Alignment(horizontal='center', vertical='center')
        
        thin_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment
            cell.border = thin_border
        
        row = 2
        for json_file in self.data_dir.glob('*_list.json'):
            account_name = json_file.stem.replace('_list', '')
            
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            articles = data.get('articles', [])
            total = len(articles)
            downloaded = sum(1 for a in articles if a.get('downloaded'))
            not_downloaded = total - downloaded
            fetched_at = data.get('fetched_at', '')[:19]
            
            ws.cell(row=row, column=1, value=account_name)
            ws.cell(row=row, column=2, value=total)
            ws.cell(row=row, column=3, value=downloaded)
            ws.cell(row=row, column=4, value=not_downloaded)
            ws.cell(row=row, column=5, value=fetched_at)
            
            for col in range(1, len(headers) + 1):
                ws.cell(row=row, column=col).border = thin_border
            
            row += 1
        
        column_widths = [20, 12, 12, 12, 25]
        for col, width in enumerate(column_widths, 1):
            ws.column_dimensions[get_column_letter(col)].width = width
        
        ws.row_dimensions[1].height = 25
        
        try:
            wb.save(output_file)
            print(f"[✅] 汇总文件已导出: {output_file}")
            return output_file
        except Exception as e:
            print(f"[❌] 导出失败: {e}")
            return None


def main():
    exporter = ExcelExporter()
    
    accounts = []
    for json_file in Path(DATA_DIR).glob('*_list.json'):
        account_name = json_file.stem.replace('_list', '')
        accounts.append(account_name)
    
    if not accounts:
        print("[❌] 没有已采集的公众号数据")
        return
    
    print("\n已采集的公众号:")
    for i, acc in enumerate(accounts, 1):
        print(f"  {i}) {acc}")
    
    print(f"\n请选择导出方式:")
    print("  1) 导出所有公众号")
    print("  2) 导出单个公众号")
    print("  3) 导出汇总表")
    
    choice = input("\n请输入选项: ").strip()
    
    if choice == '1':
        files = exporter.export_all()
        print(f"\n[📊] 共导出 {len(files)} 个文件")
    elif choice == '2':
        if accounts:
            name = input("请输入公众号名称: ").strip()
            if name in accounts:
                exporter.export_account(name)
            else:
                print("[❌] 无效的公众号名称")
    elif choice == '3':
        exporter.export_summary()
    else:
        print("[❌] 无效选项")


if __name__ == "__main__":
    main()
