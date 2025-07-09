#!/usr/bin/env python3
"""
Dark Web Scraper with GUI
Educational tool for crawling .onion sites via Tor
Author: AI Assistant
Version: 1.1 (Target URL replaced with Custom Words)
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
from bs4 import BeautifulSoup
import requests
import pandas as pd
import time
import json
import threading
import logging
from typing import List, Dict, Optional
from datetime import datetime
import sys
import queue
import re

TOR_SOCKS_PROXY = 'socks5h://127.0.0.1:9050'

class DarkWebScraper:
    """Core dark web scraping functionality using Tor."""

    def __init__(self, delay: float = 2.0, max_items: int = 20, max_depth: int = 1):
        self.delay = delay
        self.max_items = max_items
        self.max_depth = max_depth
        self.session = requests.Session()
        self.session.proxies = {
            'http': TOR_SOCKS_PROXY,
            'https': TOR_SOCKS_PROXY
        }
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)

    def get_page(self, url: str) -> Optional[BeautifulSoup]:
        # Only allow .onion
        if not url.startswith("http://") and not url.startswith("https://"):
            self.logger.error(f"Invalid scheme for URL: {url}")
            return None
        if ".onion" not in url:
            self.logger.warning(f"Non-onion address skipped: {url}")
            return None
        try:
            resp = self.session.get(url, timeout=25)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.content, 'html.parser')
            time.sleep(self.delay)
            return soup
        except Exception as e:
            self.logger.error(f"Failed to fetch {url}: {e}")
            return None

    def extract_onion_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        links = set()
        for a in soup.find_all('a', href=True):
            href = a['href']
            if ".onion" in href:
                # Absolute or relative
                if href.startswith("http"):
                    links.add(href)
                elif href.startswith("/"):
                    onion_host = re.match(r"(http[s]?://[^/]+)", base_url)
                    if onion_host:
                        links.add(onion_host.group(1) + href)
        return list(links)

    def scrape_content(self, url: str, keywords: List[str] = None, selectors: List[str] = None) -> List[Dict]:
        """Scrape a single .onion page for text, links, and optionally filter by keywords or selectors."""
        soup = self.get_page(url)
        if not soup:
            return []
        data = []
        elements = []
        if selectors:
            # Use the first selector with matches
            for sel in selectors:
                found = soup.select(sel)
                if found:
                    elements = found[:self.max_items]
                    break
        if not elements:
            elements = soup.find_all(['p', 'div', 'span', 'h1', 'h2', 'li'], limit=self.max_items)
        for elem in elements:
            try:
                text = elem.get_text(strip=True)
                if not text or len(text) < 20:
                    continue
                if keywords and not any(kw.lower() in text.lower() for kw in keywords):
                    continue
                link = ""
                a_tag = elem.find('a') or elem.find_parent('a')
                if a_tag and a_tag.get('href'):
                    link = a_tag['href']
                data.append({
                    'text': text[:500],
                    'link': link,
                    'tag': elem.name,
                    'source': url,
                })
            except Exception as e:
                self.logger.error(f"Error parsing element: {e}")
        return data

    def crawl_onion(self, start_urls: List[str], keywords: List[str] = None, selectors: List[str] = None,
                    max_pages: int = 30) -> List[Dict]:
        """Crawl .onion domains starting from a seed list, following .onion links, breadth-first."""
        visited = set()
        results = []
        q = queue.Queue()
        for url in start_urls:
            q.put((url, 0))
        pages_crawled = 0
        while not q.empty() and pages_crawled < max_pages:
            url, depth = q.get()
            if url in visited or depth > self.max_depth:
                continue
            visited.add(url)
            self.logger.info(f"Crawling {url} (depth {depth})")
            soup = self.get_page(url)
            if soup:
                # Scrape current
                page_data = self.scrape_content(url, keywords=keywords, selectors=selectors)
                results.extend(page_data)
                # Find new .onion links
                if depth < self.max_depth:
                    for link in self.extract_onion_links(soup, url):
                        if link not in visited:
                            q.put((link, depth + 1))
            pages_crawled += 1
        return results[:self.max_items]

    def search_onion_directories(self, custom_words: str, num_results: int = 5) -> List[str]:
        """
        Search onion directories (like Ahmia) for .onion sites matching custom words.
        For demonstration, this will use Ahmia's clearnet search.
        """
        # Note: This is a basic example using https://ahmia.fi/search/?q=...
        # In reality, you might want to use other directories or more advanced crawling.
        results = []
        try:
            url = f"https://ahmia.fi/search/?q={requests.utils.quote(custom_words)}"
            resp = requests.get(url, timeout=15)
            soup = BeautifulSoup(resp.content, 'html.parser')
            for a in soup.select('.result .title a'):
                href = a.get('href')
                if href and ".onion" in href:
                    results.append(href)
                if len(results) >= num_results:
                    break
            time.sleep(self.delay)
        except Exception as e:
            self.logger.error(f"Failed to search Ahmia for custom words: {e}")
        return results


class DarkWebScraperGUI:
    """GUI for the dark web scraper."""

    def __init__(self, root):
        self.root = root
        self.root.title("Dark Web Scraper (Educational)")
        self.root.geometry("1200x700")
        self.root.configure(bg='#202124')
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.configure_styles()
        self.scraper = None
        self.scraped_data = []
        self.is_scraping = False
        self.setup_logging()
        self.create_widgets()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def configure_styles(self):
        self.style.configure('Heading.TLabel', font=('Arial', 11, 'bold'), background='#202124', foreground='#ffe082')
        self.style.configure('Custom.TButton', font=('Arial', 10, 'bold'))
        self.style.configure('Start.TButton',
            font=('Arial', 14, 'bold'),
            foreground='#ffffff',
            background='#43a047',
            borderwidth=3,
            focusthickness=3,
            focuscolor='red'
        )
        self.style.map('Start.TButton',
            background=[('active', '#2e7d32'), ('!active', '#43a047')]
        )
        self.style.configure('Stop.TButton', font=('Arial', 10, 'bold'), foreground='#e57373')
        self.style.configure('Export.TButton', font=('Arial', 9), foreground='#64b5f6')

    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('darkweb_scraper.log')
            ]
        )
        self.logger = logging.getLogger(__name__)

    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        self.create_settings_panel(main_frame)
        self.create_results_panel(main_frame)
        self.create_log_panel(main_frame)
        main_frame.rowconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        main_frame.rowconfigure(2, weight=0)

    def create_settings_panel(self, parent):
        settings_frame = ttk.LabelFrame(parent, text="🕸️ Dark Web Scraper Settings", padding="10")
        settings_frame.grid(row=0, column=0, sticky=(tk.N, tk.W, tk.E), padx=(0, 10), pady=(0, 10))
        # Custom Words for Onion Search
        ttk.Label(settings_frame, text="🔤 Custom Words to Find Onion Sites:", style='Heading.TLabel').grid(row=0, column=0, sticky=tk.W, pady=(0, 2))
        self.custom_words_var = tk.StringVar(value="forum drugs news market")
        self.custom_words_entry = ttk.Entry(settings_frame, textvariable=self.custom_words_var, width=60, font=('Arial', 10))
        self.custom_words_entry.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 8))
        # Max Depth
        ttk.Label(settings_frame, text="🔀 Crawl Depth:", style='Heading.TLabel').grid(row=2, column=0, sticky=tk.W, pady=(0, 2))
        self.depth_var = tk.IntVar(value=1)
        depth_spin = tk.Spinbox(settings_frame, from_=0, to=3, increment=1, textvariable=self.depth_var, width=8)
        depth_spin.grid(row=3, column=0, sticky=tk.W, pady=(0, 8))
        # Delay and Max Items
        ttk.Label(settings_frame, text="⏱️ Delay (s):", style='Heading.TLabel').grid(row=2, column=1, sticky=tk.W, pady=(0, 2))
        self.delay_var = tk.DoubleVar(value=2.0)
        delay_spin = tk.Spinbox(settings_frame, from_=1.0, to=15.0, increment=0.5, textvariable=self.delay_var, width=8)
        delay_spin.grid(row=3, column=1, sticky=tk.W, pady=(0, 8))
        ttk.Label(settings_frame, text="📊 Max Items:", style='Heading.TLabel').grid(row=4, column=0, sticky=tk.W, pady=(0, 2))
        self.max_items_var = tk.IntVar(value=20)
        items_spin = tk.Spinbox(settings_frame, from_=1, to=100, increment=1, textvariable=self.max_items_var, width=8)
        items_spin.grid(row=5, column=0, sticky=tk.W, pady=(0, 8))
        # CSS Selectors (small box)
        ttk.Label(settings_frame, text="🎯 CSS Selectors (optional):", style='Heading.TLabel').grid(row=6, column=0, sticky=tk.W, pady=(0, 2))
        self.selectors_text = scrolledtext.ScrolledText(settings_frame, width=24, height=3, font=('Consolas', 9))
        self.selectors_text.grid(row=7, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 8))
        # Keywords
        ttk.Label(settings_frame, text="🔑 Keywords (comma separated, optional):", style='Heading.TLabel').grid(row=8, column=0, sticky=tk.W, pady=(0, 2))
        self.keywords_var = tk.StringVar(value="")
        self.keywords_entry = ttk.Entry(settings_frame, textvariable=self.keywords_var, width=40, font=('Arial', 10))
        self.keywords_entry.grid(row=9, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 8))
        # Buttons
        button_frame = ttk.Frame(settings_frame)
        button_frame.grid(row=10, column=0, columnspan=2, pady=(10, 0), sticky=tk.EW)
        self.start_button = ttk.Button(
            button_frame,
            text="▶️ START CRAWLING",
            command=self.start_scraping,
            style='Start.TButton',
            width=18
        )
        self.start_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 8), ipadx=8, ipady=6)
        self.stop_button = ttk.Button(button_frame, text="⏹️ Stop",
                                      command=self.stop_scraping, state=tk.DISABLED, style='Stop.TButton', width=10)
        self.stop_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 8))
        self.clear_button = ttk.Button(button_frame, text="🗑️ Clear Results",
                                       command=self.clear_results, width=14)
        self.clear_button.pack(side=tk.LEFT, expand=True, fill=tk.X)

    def create_results_panel(self, parent):
        results_frame = ttk.LabelFrame(parent, text="📊 Crawling Results", padding="10")
        results_frame.grid(row=0, column=1, columnspan=2, sticky=(tk.N, tk.S, tk.E, tk.W), pady=(0, 10))
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(2, weight=1)
        progress_frame = ttk.Frame(results_frame)
        progress_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 8))
        progress_frame.columnconfigure(1, weight=1)
        self.progress_var = tk.StringVar(value="Ready to crawl dark web...")
        progress_label = ttk.Label(progress_frame, textvariable=self.progress_var, font=('Arial', 10, 'bold'))
        progress_label.grid(row=0, column=0, sticky=tk.W)
        self.progress_bar = ttk.Progressbar(progress_frame, mode='indeterminate')
        self.progress_bar.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(15, 0))
        stats_frame = ttk.Frame(results_frame)
        stats_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 8))
        self.stats_var = tk.StringVar(value="Items found: 0 | Total scraped: 0")
        stats_label = ttk.Label(stats_frame, textvariable=self.stats_var, font=('Arial', 9))
        stats_label.grid(row=0, column=0, sticky=tk.W)
        columns = ('Text', 'Link', 'Tag', 'Source')
        self.results_tree = ttk.Treeview(results_frame, columns=columns, show='headings', height=18)
        column_widths = {'Text': 350, 'Link': 200, 'Tag': 80, 'Source': 200}
        for col in columns:
            self.results_tree.heading(col, text=col, command=lambda c=col: self.sort_treeview(c))
            self.results_tree.column(col, width=column_widths.get(col, 150), anchor='w')
        v_scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=self.results_tree.yview)
        h_scrollbar = ttk.Scrollbar(results_frame, orient=tk.HORIZONTAL, command=self.results_tree.xview)
        self.results_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        self.results_tree.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        v_scrollbar.grid(row=2, column=1, sticky=(tk.N, tk.S))
        h_scrollbar.grid(row=3, column=0, sticky=(tk.W, tk.E))
        export_frame = ttk.Frame(results_frame)
        export_frame.grid(row=4, column=0, columnspan=2, pady=(10, 0), sticky=tk.EW)
        ttk.Button(export_frame, text="📁 Export CSV", command=self.export_csv, style='Export.TButton').pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 8))
        ttk.Button(export_frame, text="📄 Export JSON", command=self.export_json, style='Export.TButton').pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 8))
        ttk.Button(export_frame, text="🔍 View Details", command=self.view_details, style='Export.TButton').pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 8))
        ttk.Button(export_frame, text="📊 Statistics", command=self.show_statistics, style='Export.TButton').pack(side=tk.LEFT, expand=True, fill=tk.X)

    def create_log_panel(self, parent):
        log_frame = ttk.LabelFrame(parent, text="📝 Activity Log", padding="8")
        log_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 0))
        log_frame.columnconfigure(0, weight=1)
        self.log_text = scrolledtext.ScrolledText(log_frame, height=8, width=120, font=('Consolas', 9), bg="#181a1b", fg="#ffe082")
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        log_button_frame = ttk.Frame(log_frame)
        log_button_frame.grid(row=1, column=0, pady=(6, 0), sticky=tk.EW)
        ttk.Button(log_button_frame, text="Clear Log", command=self.clear_log).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 8))
        ttk.Button(log_button_frame, text="Save Log", command=self.save_log).pack(side=tk.LEFT, expand=True, fill=tk.X)

    def get_custom_selectors(self) -> List[str]:
        selectors_text = self.selectors_text.get(1.0, tk.END).strip()
        if not selectors_text:
            return []
        selectors = []
        for line in selectors_text.split('\n'):
            line = line.strip()
            if line and not line.startswith('#'):
                selectors.append(line)
        return selectors

    def log_message(self, message, level="INFO"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {level}: {message}\n"
        self.log_text.insert(tk.END, log_entry)
        self.log_text.see(tk.END)
        self.root.update_idletasks()
        self.logger.info(message)

    def sort_treeview(self, col):
        data = [(self.results_tree.set(child, col), child) for child in self.results_tree.get_children('')]
        data.sort()
        for index, (val, child) in enumerate(data):
            self.results_tree.move(child, '', index)

    def start_scraping(self):
        if self.is_scraping:
            messagebox.showwarning("Warning", "Crawling is already in progress!")
            return
        custom_words = self.custom_words_var.get().strip()
        if not custom_words:
            messagebox.showerror("Error", "Please enter custom words to search for .onion sites!")
            return
        self.is_scraping = True
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.progress_bar.start()
        self.progress_var.set("🔄 Searching directories and crawling...")
        self.log_message(f"Searching for onion sites with: {custom_words}")
        threading.Thread(target=self.scrape_data, daemon=True).start()

    def stop_scraping(self):
        self.is_scraping = False
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.progress_bar.stop()
        self.progress_var.set("⏹️ Crawling stopped by user")
        self.log_message("Crawling stopped by user", "WARNING")

    def scrape_data(self):
        try:
            custom_words = self.custom_words_var.get().strip()
            keywords = [w.strip() for w in self.keywords_var.get().split(',') if w.strip()]
            selectors = self.get_custom_selectors()
            self.scraper = DarkWebScraper(
                delay=self.delay_var.get(),
                max_items=self.max_items_var.get(),
                max_depth=self.depth_var.get()
            )
            self.root.after(0, lambda: self.log_message("Initialized dark web scraper"))
            onion_urls = self.scraper.search_onion_directories(custom_words, num_results=10)
            if not onion_urls:
                self.root.after(0, lambda: self.log_message("No .onion URLs found for given words.", "WARNING"))
                self.root.after(0, self.scraping_finished)
                return
            self.root.after(0, lambda: self.log_message(f"Found {len(onion_urls)} seed .onion URLs. Starting crawl..."))
            data = self.scraper.crawl_onion(onion_urls, keywords=keywords if keywords else None, selectors=selectors if selectors else None, max_pages=100)
            self.root.after(0, lambda: self.update_results(data))
        except Exception as e:
            error_msg = f"Crawling error: {str(e)}"
            self.root.after(0, lambda: self.log_message(error_msg, "ERROR"))
            self.root.after(0, lambda: messagebox.showerror("Crawling Error", error_msg))
        finally:
            self.root.after(0, self.scraping_finished)

    def scraping_finished(self):
        self.is_scraping = False
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.progress_bar.stop()
        self.progress_var.set("✅ Crawling completed")

    def update_results(self, data):
        if not data:
            self.log_message("No data found during crawl", "WARNING")
            return
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        self.scraped_data = data
        for item in data:
            if not self.is_scraping:
                break
            try:
                self.results_tree.insert('', tk.END, values=(
                    item.get('text', '')[:100],
                    item.get('link', '')[:80],
                    item.get('tag', ''),
                    item.get('source', '')[:60]
                ))
            except Exception as e:
                self.log_message(f"Error adding item to results: {e}", "ERROR")
        total_items = len(data)
        self.stats_var.set(f"Items found: {total_items} | Total scraped: {len(self.scraped_data)}")
        self.log_message(f"Successfully crawled {total_items} items")

    def clear_results(self):
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        self.scraped_data = []
        self.stats_var.set("Items found: 0 | Total scraped: 0")
        self.progress_var.set("Ready to crawl dark web...")
        self.log_message("Results cleared")

    def export_csv(self):
        if not self.scraped_data:
            messagebox.showwarning("Warning", "No data to export!")
            return
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Save CSV File"
        )
        if filename:
            try:
                df = pd.DataFrame(self.scraped_data)
                df.to_csv(filename, index=False, encoding='utf-8')
                self.log_message(f"Data exported to CSV: {filename}")
                messagebox.showinfo("Success", f"Data exported successfully to:\n{filename}")
            except Exception as e:
                error_msg = f"Error exporting CSV: {str(e)}"
                self.log_message(error_msg, "ERROR")
                messagebox.showerror("Export Error", error_msg)

    def export_json(self):
        if not self.scraped_data:
            messagebox.showwarning("Warning", "No data to export!")
            return
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Save JSON File"
        )
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(self.scraped_data, f, indent=2, ensure_ascii=False)
                self.log_message(f"Data exported to JSON: {filename}")
                messagebox.showinfo("Success", f"Data exported successfully to:\n{filename}")
            except Exception as e:
                error_msg = f"Error exporting JSON: {str(e)}"
                self.log_message(error_msg, "ERROR")
                messagebox.showerror("Export Error", error_msg)

    def view_details(self):
        selection = self.results_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an item to view details!")
            return
        item_index = self.results_tree.index(selection[0])
        if item_index < len(self.scraped_data):
            item_data = self.scraped_data[item_index]
            details_window = tk.Toplevel(self.root)
            details_window.title("Item Details")
            details_window.geometry("800x600")
            details_window.configure(bg='#181a1b')
            details_frame = ttk.Frame(details_window, padding="20")
            details_frame.pack(fill=tk.BOTH, expand=True)
            details_text = scrolledtext.ScrolledText(details_frame, width=80, height=30, font=('Consolas', 10), bg="#181a1b", fg="#ffe082")
            details_text.pack(fill=tk.BOTH, expand=True)
            details_content = "ITEM DETAILS\n" + "="*50 + "\n\n"
            for key, value in item_data.items():
                details_content += f"{key.upper()}: {value}\n\n"
            details_text.insert(tk.END, details_content)
            details_text.config(state=tk.DISABLED)

    def show_statistics(self):
        if not self.scraped_data:
            messagebox.showwarning("Warning", "No data to analyze!")
            return
        stats = {
            'Total Items': len(self.scraped_data),
            'Tags': {},
            'Sources': {},
            'Items with Links': 0,
            'Average Text Length': 0
        }
        text_lengths = []
        for item in self.scraped_data:
            tag = item.get('tag', 'unknown')
            stats['Tags'][tag] = stats['Tags'].get(tag, 0) + 1
            source = item.get('source', 'unknown')
            stats['Sources'][source] = stats['Sources'].get(source, 0) + 1
            if item.get('link'):
                stats['Items with Links'] += 1
            text_content = item.get('text', '')
            if text_content:
                text_lengths.append(len(text_content))
        if text_lengths:
            stats['Average Text Length'] = sum(text_lengths) / len(text_lengths)
        stats_window = tk.Toplevel(self.root)
        stats_window.title("Crawling Statistics")
        stats_window.geometry("600x500")
        stats_window.configure(bg='#181a1b')
        stats_frame = ttk.Frame(stats_window, padding="20")
        stats_frame.pack(fill=tk.BOTH, expand=True)
        stats_text = scrolledtext.ScrolledText(stats_frame, width=70, height=25, font=('Consolas', 10), bg="#181a1b", fg="#ffe082")
        stats_text.pack(fill=tk.BOTH, expand=True)
        stats_content = "CRAWLING STATISTICS\n" + "="*50 + "\n\n"
        stats_content += f"Total Items Scraped: {stats['Total Items']}\n"
        stats_content += f"Items with Links: {stats['Items with Links']}\n"
        stats_content += f"Average Text Length: {stats['Average Text Length']:.1f} characters\n\n"
        stats_content += "TAGS:\n" + "-"*20 + "\n"
        for tag, count in stats['Tags'].items():
            stats_content += f"{tag.title()}: {count}\n"
        stats_content += "\nSOURCES:\n" + "-"*20 + "\n"
        for source, count in stats['Sources'].items():
            stats_content += f"{source}: {count}\n"
        stats_text.insert(tk.END, stats_content)
        stats_text.config(state=tk.DISABLED)

    def clear_log(self):
        self.log_text.delete(1.0, tk.END)

    def save_log(self):
        log_content = self.log_text.get(1.0, tk.END)
        if not log_content.strip():
            messagebox.showwarning("Warning", "No log content to save!")
            return
        filename = filedialog.asksaveasfilename(
            defaultextension=".log",
            filetypes=[("Log files", "*.log"), ("Text files", "*.txt"), ("All files", "*.*")],
            title="Save Log File"
        )
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(log_content)
                messagebox.showinfo("Success", f"Log saved successfully to:\n{filename}")
            except Exception as e:
                messagebox.showerror("Save Error", f"Error saving log: {str(e)}")

    def on_closing(self):
        if self.is_scraping:
            if messagebox.askokcancel("Quit", "Crawling is in progress. Do you want to quit?"):
                self.is_scraping = False
                self.root.destroy()
        else:
            self.root.destroy()

def main():
    try:
        root = tk.Tk()
        app = DarkWebScraperGUI(root)
        menubar = tk.Menu(root)
        root.config(menu=menubar)
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="New Session", command=app.clear_results)
        file_menu.add_separator()
        file_menu.add_command(label="Export CSV", command=app.export_csv)
        file_menu.add_command(label="Export JSON", command=app.export_json)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=root.quit)
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="Statistics", command=app.show_statistics)
        tools_menu.add_command(label="Clear Log", command=app.clear_log)
        tools_menu.add_command(label="Save Log", command=app.save_log)
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=lambda: messagebox.showinfo(
            "About",
            "Dark Web Scraper v1.1 (Educational)\n\n"
            "A tool for crawling .onion domains via Tor.\n"
            "⚠️ For educational/research purposes only. Do not scrape or download illegal content.\n"
            "Always use with proper precautions."
        ))
        root.mainloop()
    except Exception as e:
        print(f"Error starting application: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()