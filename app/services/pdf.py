"""Сервис генерации PDF."""

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from jinja2 import Environment, FileSystemLoader
from loguru import logger
from weasyprint import HTML, CSS

from app.config import get_settings

settings = get_settings()


class PDFService:
    """Сервис для генерации PDF документов."""

    def __init__(self):
        self.templates_dir = Path("app/templates/pdf")
        self.output_dir = Path("output/pdf")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Настройка Jinja2
        self.jinja_env = Environment(
            loader=FileSystemLoader(self.templates_dir),
            autoescape=True,
        )

    def generate_plan_pdf(self, plan_data: Dict[str, Any]) -> str:
        """Генерация PDF плана смены."""
        try:
            # Загружаем шаблон
            template = self.jinja_env.get_template("plan.html.j2")
            
            # Подготавливаем данные для шаблона
            template_data = {
                "title": "План смены",
                "date": datetime.now().strftime("%d.%m.%Y"),
                "time": datetime.now().strftime("%H:%M"),
                "plan_data": plan_data,
                "generated_at": datetime.now().isoformat(),
            }
            
            # Рендерим HTML
            html_content = template.render(**template_data)
            
            # Загружаем CSS
            css_path = self.templates_dir / "lpa.css"
            css_content = ""
            if css_path.exists():
                css_content = css_path.read_text(encoding="utf-8")
            
            # Генерируем PDF
            output_filename = f"plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            output_path = self.output_dir / output_filename
            
            HTML(string=html_content).write_pdf(
                output_path,
                stylesheets=[CSS(string=css_content)] if css_content else None,
            )
            
            logger.info(f"Plan PDF generated: {output_path}")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"Error generating plan PDF: {e}")
            raise

    def generate_report_pdf(self, report_data: Dict[str, Any]) -> str:
        """Генерация PDF отчёта."""
        try:
            # Загружаем шаблон
            template = self.jinja_env.get_template("report.html.j2")
            
            # Подготавливаем данные для шаблона
            template_data = {
                "title": "Отчёт по смене",
                "date": datetime.now().strftime("%d.%m.%Y"),
                "time": datetime.now().strftime("%H:%M"),
                "report_data": report_data,
                "generated_at": datetime.now().isoformat(),
            }
            
            # Рендерим HTML
            html_content = template.render(**template_data)
            
            # Загружаем CSS
            css_path = self.templates_dir / "lpa.css"
            css_content = ""
            if css_path.exists():
                css_content = css_path.read_text(encoding="utf-8")
            
            # Генерируем PDF
            output_filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            output_path = self.output_dir / output_filename
            
            HTML(string=html_content).write_pdf(
                output_path,
                stylesheets=[CSS(string=css_content)] if css_content else None,
            )
            
            logger.info(f"Report PDF generated: {output_path}")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"Error generating report PDF: {e}")
            raise

    def generate_lpa_pdf(self, lpa_data: Dict[str, Any]) -> str:
        """Генерация PDF ЛПА из DOCX шаблона."""
        try:
            from .lpa_pdf import render_lpa_pdf
            
            template_path = self.templates_dir / "lpa_template.docx"
            if not template_path.exists():
                raise FileNotFoundError(f"LPA template not found: {template_path}")
            
            pdf_path = render_lpa_pdf(
                template_path=str(template_path),
                out_dir=str(self.output_dir),
                data=lpa_data,
                filename_prefix="LPA"
            )
            
            logger.info(f"LPA PDF generated: {pdf_path}")
            return pdf_path
            
        except Exception as e:
            logger.error(f"Error generating LPA PDF: {e}")
            raise

    def generate_efficiency_pdf(self, efficiency_data: Dict[str, Any]) -> str:
        """Генерация PDF отчёта по эффективности."""
        try:
            # Загружаем шаблон
            template = self.jinja_env.get_template("efficiency.html.j2")
            
            # Подготавливаем данные для шаблона
            template_data = {
                "title": "Отчёт по эффективности",
                "date": datetime.now().strftime("%d.%m.%Y"),
                "time": datetime.now().strftime("%H:%M"),
                "efficiency_data": efficiency_data,
                "generated_at": datetime.now().isoformat(),
            }
            
            # Рендерим HTML
            html_content = template.render(**template_data)
            
            # Загружаем CSS
            css_path = self.templates_dir / "lpa.css"
            css_content = ""
            if css_path.exists():
                css_content = css_path.read_text(encoding="utf-8")
            
            # Генерируем PDF
            output_filename = f"efficiency_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            output_path = self.output_dir / output_filename
            
            HTML(string=html_content).write_pdf(
                output_path,
                stylesheets=[CSS(string=css_content)] if css_content else None,
            )
            
            logger.info(f"Efficiency PDF generated: {output_path}")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"Error generating efficiency PDF: {e}")
            raise

    def cleanup_old_files(self, days: int = 7):
        """Очистка старых PDF файлов."""
        try:
            cutoff_time = datetime.now().timestamp() - (days * 24 * 60 * 60)
            
            for file_path in self.output_dir.glob("*.pdf"):
                if file_path.stat().st_mtime < cutoff_time:
                    file_path.unlink()
                    logger.info(f"Deleted old PDF file: {file_path}")
            
        except Exception as e:
            logger.error(f"Error cleaning up old PDF files: {e}")


# Глобальный экземпляр сервиса
pdf_service = PDFService()
