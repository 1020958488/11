#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub仓库管理软件

功能特性：
1. 仓库文件浏览和管理
2. 文件编辑和预览
3. 文件上传下载
4. 提交历史查看
5. 分支管理
6. 图形化界面
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import requests
import json
import base64
import os
from datetime import datetime
from typing import Dict, List, Optional
import webbrowser
import re

# 可选依赖，如果不可用则提供降级方案
try:
    import markdown
    MARKDOWN_AVAILABLE = True
except ImportError:
    MARKDOWN_AVAILABLE = False

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    from io import BytesIO
    BYTES_IO_AVAILABLE = True
except ImportError:
    BYTES_IO_AVAILABLE = False

class GitHubRepoManager:
    """GitHub仓库管理器"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("GitHub仓库管理软件")
        self.root.geometry("1200x800")
        
        # GitHub配置
        self.token = ""
        self.repo = ""
        self.current_branch = "main"
        self.headers = {}
        
        # 当前文件信息
        self.current_file_path = ""
        self.current_file_content = ""
        self.current_file_sha = ""
        
        self.setup_ui()
        self.check_git_integration()
    
    def setup_ui(self):
        """设置用户界面"""
        # 主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 配置区域
        config_frame = ttk.LabelFrame(main_frame, text="GitHub配置", padding="10")
        config_frame.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Token输入
        ttk.Label(config_frame, text="GitHub Token:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.token_entry = ttk.Entry(config_frame, width=50, show="*")
        self.token_entry.grid(row=0, column=1, padx=(0, 10))
        
        # 仓库输入
        ttk.Label(config_frame, text="仓库 (owner/repo):").grid(row=1, column=0, sticky=tk.W, padx=(0, 10))
        self.repo_entry = ttk.Entry(config_frame, width=50)
        self.repo_entry.grid(row=1, column=1, padx=(0, 10))
        
        # 分支选择
        ttk.Label(config_frame, text="分支:").grid(row=2, column=0, sticky=tk.W, padx=(0, 10))
        self.branch_combo = ttk.Combobox(config_frame, width=47, state="readonly")
        self.branch_combo.grid(row=2, column=1, padx=(0, 10))
        self.branch_combo.bind("<<ComboboxSelected>>", self.on_branch_change)
        
        # 连接按钮
        self.connect_btn = ttk.Button(config_frame, text="连接仓库", command=self.connect_repo)
        self.connect_btn.grid(row=0, column=2, rowspan=3, sticky=(tk.N, tk.S), padx=(10, 0))
        
        # 文件搜索区域
        search_frame = ttk.Frame(main_frame)
        search_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Label(search_frame, text="搜索文件:").pack(side=tk.LEFT, padx=(0, 10))
        self.search_entry = ttk.Entry(search_frame, width=40)
        self.search_entry.pack(side=tk.LEFT, padx=(0, 10))
        self.search_entry.bind("<KeyRelease>", self.on_search_change)
        
        ttk.Button(search_frame, text="搜索", command=self.search_files).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(search_frame, text="清除", command=self.clear_search).pack(side=tk.LEFT)
        
        # 主要内容区域
        content_frame = ttk.Frame(main_frame)
        content_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 文件浏览器（左侧）
        file_frame = ttk.LabelFrame(content_frame, text="文件浏览器", padding="10")
        file_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 10))
        
        # 文件树
        self.file_tree = ttk.Treeview(file_frame, height=20)
        self.file_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 文件树滚动条
        file_scrollbar = ttk.Scrollbar(file_frame, orient=tk.VERTICAL, command=self.file_tree.yview)
        file_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.file_tree.configure(yscrollcommand=file_scrollbar.set)
        
        # 绑定文件选择事件
        self.file_tree.bind("<<TreeviewSelect>>", self.on_file_select)
        
        # 文件操作按钮
        file_btn_frame = ttk.Frame(file_frame)
        file_btn_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(file_btn_frame, text="刷新", command=self.refresh_files).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(file_btn_frame, text="新建文件", command=self.create_file).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(file_btn_frame, text="上传文件", command=self.upload_file).pack(side=tk.LEFT)
        
        # 文件编辑/预览区域（右侧）
        editor_frame = ttk.LabelFrame(content_frame, text="文件编辑/预览", padding="10")
        editor_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 文件路径显示和预览模式切换
        path_frame = ttk.Frame(editor_frame)
        path_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.file_path_label = ttk.Label(path_frame, text="未选择文件", font=("Arial", 10, "bold"))
        self.file_path_label.pack(side=tk.LEFT)
        
        # 预览模式选择
        self.preview_mode = tk.StringVar(value="edit")
        mode_frame = ttk.Frame(path_frame)
        mode_frame.pack(side=tk.RIGHT)
        
        ttk.Radiobutton(mode_frame, text="编辑", variable=self.preview_mode, value="edit", 
                       command=self.switch_preview_mode).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Radiobutton(mode_frame, text="预览", variable=self.preview_mode, value="preview", 
                       command=self.switch_preview_mode).pack(side=tk.LEFT)
        
        # 文件内容区域（使用Notebook来切换不同视图）
        self.content_notebook = ttk.Notebook(editor_frame)
        self.content_notebook.pack(fill=tk.BOTH, expand=True)
        
        # 文本编辑页面
        edit_frame = ttk.Frame(self.content_notebook)
        self.content_notebook.add(edit_frame, text="文本编辑")
        
        self.file_text = tk.Text(edit_frame, wrap=tk.NONE, width=60, height=20)
        self.file_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        text_scrollbar = ttk.Scrollbar(edit_frame, orient=tk.VERTICAL, command=self.file_text.yview)
        text_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.file_text.configure(yscrollcommand=text_scrollbar.set)
        
        # 预览页面
        preview_frame = ttk.Frame(self.content_notebook)
        self.content_notebook.add(preview_frame, text="文件预览")
        
        self.preview_text = tk.Text(preview_frame, wrap=tk.WORD, width=60, height=20, state=tk.DISABLED)
        self.preview_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        preview_scrollbar = ttk.Scrollbar(preview_frame, orient=tk.VERTICAL, command=self.preview_text.yview)
        preview_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.preview_text.configure(yscrollcommand=preview_scrollbar.set)
        
        # 图片预览页面
        image_frame = ttk.Frame(self.content_notebook)
        self.content_notebook.add(image_frame, text="图片预览")
        
        self.image_label = ttk.Label(image_frame, text="图片预览区域")
        self.image_label.pack(expand=True)
        
        # 文件操作按钮
        editor_btn_frame = ttk.Frame(editor_frame)
        editor_btn_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(editor_btn_frame, text="保存文件", command=self.save_file).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(editor_btn_frame, text="下载文件", command=self.download_file).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(editor_btn_frame, text="删除文件", command=self.delete_file).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(editor_btn_frame, text="在GitHub中查看", command=self.view_on_github).pack(side=tk.LEFT)
        
        # 提交历史和分支管理区域
        bottom_frame = ttk.Frame(content_frame)
        bottom_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(10, 0))
        
        # 提交历史（左下）
        history_frame = ttk.LabelFrame(bottom_frame, text="提交历史", padding="10")
        history_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        self.history_tree = ttk.Treeview(history_frame, height=8)
        self.history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        history_scrollbar = ttk.Scrollbar(history_frame, orient=tk.VERTICAL, command=self.history_tree.yview)
        history_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.history_tree.configure(yscrollcommand=history_scrollbar.set)
        
        # 绑定提交选择事件
        self.history_tree.bind("<<TreeviewSelect>>", self.on_history_select)
        
        # 分支管理（右下）
        branch_frame = ttk.LabelFrame(bottom_frame, text="分支管理", padding="10")
        branch_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        self.branch_tree = ttk.Treeview(branch_frame, height=8)
        self.branch_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        branch_scrollbar = ttk.Scrollbar(branch_frame, orient=tk.VERTICAL, command=self.branch_tree.yview)
        branch_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.branch_tree.configure(yscrollcommand=branch_scrollbar.set)
        
        # 分支操作按钮
        branch_btn_frame = ttk.Frame(branch_frame)
        branch_btn_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(branch_btn_frame, text="刷新历史", command=self.load_commit_history).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(branch_btn_frame, text="创建分支", command=self.create_branch).pack(side=tk.LEFT)
        
        # 状态栏
        self.status_frame = ttk.Frame(main_frame)
        self.status_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(10, 0))
        
        self.status_label = ttk.Label(self.status_frame, text="就绪")
        self.status_label.pack(side=tk.LEFT)
        
        # 配置grid权重
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=3)
        main_frame.columnconfigure(2, weight=0)
        main_frame.rowconfigure(2, weight=3)
        main_frame.rowconfigure(3, weight=1)
        
        content_frame.columnconfigure(0, weight=1)
        content_frame.columnconfigure(1, weight=2)
        content_frame.rowconfigure(0, weight=2)
        content_frame.rowconfigure(1, weight=1)
        
        # 设置窗口大小调整
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
    
    def check_git_integration(self):
        """检查Git集成功能"""
        try:
            import subprocess
            result = subprocess.run(['git', '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                self.status_label.config(text="Git集成: 可用")
            else:
                self.status_label.config(text="Git集成: 未安装Git")
        except FileNotFoundError:
            self.status_label.config(text="Git集成: 未安装Git")
    
    def connect_repo(self):
        """连接到GitHub仓库"""
        token = self.token_entry.get().strip()
        repo = self.repo_entry.get().strip()
        
        if not token or not repo:
            messagebox.showwarning("警告", "请输入GitHub Token和仓库名")
            return
        
        # 验证仓库格式
        if "/" not in repo:
            messagebox.showwarning("警告", "仓库格式应为: owner/repo")
            return
        
        self.token = token
        self.repo = repo
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        # 测试连接
        try:
            response = requests.get(f"https://api.github.com/repos/{repo}", headers=self.headers)
            if response.status_code == 200:
                repo_info = response.json()
                self.status_label.config(text=f"已连接: {repo_info['full_name']}")
                self.connect_btn.config(text="重新连接", style="Success.TButton")
                
                # 获取分支列表
                self.load_branches()
                
                # 加载文件列表
                self.load_files()
                
                # 加载提交历史
                self.load_commit_history()
                
                messagebox.showinfo("成功", f"成功连接到仓库: {repo_info['full_name']}")
            else:
                messagebox.showerror("错误", f"连接失败: {response.status_code} - {response.text}")
        except Exception as e:
            messagebox.showerror("错误", f"连接失败: {str(e)}")
    
    def load_branches(self):
        """加载分支列表"""
        try:
            response = requests.get(f"https://api.github.com/repos/{self.repo}/branches", headers=self.headers)
            if response.status_code == 200:
                branches = response.json()
                branch_names = [branch['name'] for branch in branches]
                self.branch_combo['values'] = branch_names
                if branch_names:
                    self.branch_combo.set(branch_names[0])
                    self.current_branch = branch_names[0]
            else:
                messagebox.showerror("错误", f"加载分支失败: {response.status_code}")
        except Exception as e:
            messagebox.showerror("错误", f"加载分支失败: {str(e)}")
    
    def on_branch_change(self, event):
        """分支选择变化时"""
        self.current_branch = self.branch_combo.get()
        self.load_files()
    
    def load_files(self):
        """加载文件列表"""
        if not self.repo:
            return
        
        # 清空文件树
        for item in self.file_tree.get_children():
            self.file_tree.delete(item)
        
        try:
            # 获取仓库内容
            response = requests.get(
                f"https://api.github.com/repos/{self.repo}/git/trees/{self.current_branch}?recursive=1",
                headers=self.headers
            )
            
            if response.status_code == 200:
                tree_data = response.json()
                self.populate_file_tree(tree_data['tree'])
            else:
                # 尝试非递归方式
                response = requests.get(
                    f"https://api.github.com/repos/{self.repo}/contents",
                    headers=self.headers,
                    params={"ref": self.current_branch}
                )
                if response.status_code == 200:
                    contents = response.json()
                    self.populate_file_tree_simple(contents)
                else:
                    messagebox.showerror("错误", f"加载文件失败: {response.status_code}")
        except Exception as e:
            messagebox.showerror("错误", f"加载文件失败: {str(e)}")
    
    def populate_file_tree(self, tree_items):
        """填充文件树（递归模式）"""
        # 按路径排序
        sorted_items = sorted(tree_items, key=lambda x: x['path'])
        
        for item in sorted_items:
            path = item['path']
            item_type = item['type']
            
            if item_type == 'blob':  # 文件
                # 获取文件扩展名
                ext = os.path.splitext(path)[1].lower()
                icon = self.get_file_icon(ext)
                self.file_tree.insert('', 'end', text=f"{icon} {os.path.basename(path)}", 
                                    values=(path, 'file'))
            elif item_type == 'tree':  # 目录
                # 简化处理，直接显示所有文件
                pass
    
    def populate_file_tree_simple(self, contents):
        """填充文件树（简单模式）"""
        for item in contents:
            if item['type'] == 'file':
                ext = os.path.splitext(item['name'])[1].lower()
                icon = self.get_file_icon(ext)
                self.file_tree.insert('', 'end', text=f"{icon} {item['name']}", 
                                    values=(item['path'], 'file'))
            elif item['type'] == 'dir':
                self.file_tree.insert('', 'end', text=f"📁 {item['name']}", 
                                    values=(item['path'], 'dir'))
    
    def get_file_icon(self, ext):
        """获取文件图标"""
        icons = {
            '.py': '🐍', '.js': '📜', '.html': '🌐', '.css': '🎨',
            '.json': '📊', '.md': '📝', '.txt': '📄', '.yml': '⚙️',
            '.yaml': '⚙️', '.xml': '📋', '.csv': '📈', '.xlsx': '📊',
            '.jpg': '🖼️', '.png': '🖼️', '.gif': '🖼️', '.pdf': '📕',
            '.zip': '📦', '.tar': '📦', '.gz': '📦'
        }
        return icons.get(ext, '📄')
    
    def on_file_select(self, event):
        """文件选择事件"""
        selection = self.file_tree.selection()
        if not selection:
            return
        
        item = self.file_tree.item(selection[0])
        file_path = item['values'][0] if item['values'] else ''
        file_type = item['values'][1] if len(item['values']) > 1 else 'file'
        
        if file_type == 'file':
            self.load_file_content(file_path)
    
    def load_file_content(self, file_path):
        """加载文件内容"""
        try:
            response = requests.get(
                f"https://api.github.com/repos/{self.repo}/contents/{file_path}",
                headers=self.headers,
                params={"ref": self.current_branch}
            )
            
            if response.status_code == 200:
                file_data = response.json()
                content = base64.b64decode(file_data['content']).decode('utf-8')
                
                self.current_file_path = file_path
                self.current_file_content = content
                self.current_file_sha = file_data['sha']
                
                self.file_path_label.config(text=f"文件: {file_path}")
                self.file_text.delete(1.0, tk.END)
                self.file_text.insert(1.0, content)
                
                self.status_label.config(text=f"已加载: {file_path}")
            else:
                messagebox.showerror("错误", f"加载文件失败: {response.status_code}")
        except Exception as e:
            messagebox.showerror("错误", f"加载文件失败: {str(e)}")
    
    def save_file(self):
        """保存文件"""
        if not self.current_file_path:
            messagebox.showwarning("警告", "请先选择一个文件")
            return
        
        content = self.file_text.get(1.0, tk.END)
        if content == self.current_file_content:
            messagebox.showinfo("提示", "文件内容没有变化")
            return
        
        try:
            # 编码内容
            encoded_content = base64.b64encode(content.encode('utf-8')).decode('utf-8')
            
            # 准备提交数据
            commit_data = {
                "message": f"更新文件 {self.current_file_path} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "content": encoded_content,
                "sha": self.current_file_sha,
                "branch": self.current_branch
            }
            
            response = requests.put(
                f"https://api.github.com/repos/{self.repo}/contents/{self.current_file_path}",
                headers=self.headers,
                json=commit_data
            )
            
            if response.status_code in [200, 201]:
                self.current_file_content = content
                result = response.json()
                self.current_file_sha = result['content']['sha']
                
                messagebox.showinfo("成功", f"文件已保存: {self.current_file_path}")
                self.status_label.config(text=f"已保存: {self.current_file_path}")
                
                # 刷新文件列表
                self.load_files()
            else:
                messagebox.showerror("错误", f"保存文件失败: {response.status_code} - {response.text}")
        except Exception as e:
            messagebox.showerror("错误", f"保存文件失败: {str(e)}")
    
    def create_file(self):
        """创建新文件"""
        if not self.repo:
            messagebox.showwarning("警告", "请先连接到仓库")
            return
        
        # 创建对话框
        dialog = tk.Toplevel(self.root)
        dialog.title("创建新文件")
        dialog.geometry("400x300")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 文件路径
        ttk.Label(dialog, text="文件路径:").pack(anchor=tk.W, pady=(10, 5))
        path_entry = ttk.Entry(dialog, width=50)
        path_entry.pack(fill=tk.X, pady=(0, 10))
        
        # 文件内容
        ttk.Label(dialog, text="文件内容:").pack(anchor=tk.W, pady=(10, 5))
        content_text = tk.Text(dialog, width=50, height=10)
        content_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        def create():
            file_path = path_entry.get().strip()
            content = content_text.get(1.0, tk.END).strip()
            
            if not file_path:
                messagebox.showwarning("警告", "请输入文件路径")
                return
            
            try:
                # 编码内容
                encoded_content = base64.b64encode(content.encode('utf-8')).decode('utf-8')
                
                # 准备提交数据
                commit_data = {
                    "message": f"创建文件 {file_path}",
                    "content": encoded_content,
                    "branch": self.current_branch
                }
                
                response = requests.put(
                    f"https://api.github.com/repos/{self.repo}/contents/{file_path}",
                    headers=self.headers,
                    json=commit_data
                )
                
                if response.status_code == 201:
                    messagebox.showinfo("成功", f"文件已创建: {file_path}")
                    dialog.destroy()
                    self.load_files()
                else:
                    messagebox.showerror("错误", f"创建文件失败: {response.status_code} - {response.text}")
            except Exception as e:
                messagebox.showerror("错误", f"创建文件失败: {str(e)}")
        
        # 按钮
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(btn_frame, text="创建", command=create).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(btn_frame, text="取消", command=dialog.destroy).pack(side=tk.RIGHT)
    
    def delete_file(self):
        """删除文件"""
        if not self.current_file_path:
            messagebox.showwarning("警告", "请先选择一个文件")
            return
        
        if not messagebox.askyesno("确认", f"确定要删除文件 '{self.current_file_path}' 吗？"):
            return
        
        try:
            # 准备删除数据
            delete_data = {
                "message": f"删除文件 {self.current_file_path}",
                "sha": self.current_file_sha,
                "branch": self.current_branch
            }
            
            response = requests.delete(
                f"https://api.github.com/repos/{self.repo}/contents/{self.current_file_path}",
                headers=self.headers,
                json=delete_data
            )
            
            if response.status_code == 200:
                messagebox.showinfo("成功", f"文件已删除: {self.current_file_path}")
                self.current_file_path = ""
                self.current_file_content = ""
                self.current_file_sha = ""
                self.file_path_label.config(text="未选择文件")
                self.file_text.delete(1.0, tk.END)
                
                self.status_label.config(text=f"已删除: {self.current_file_path}")
                self.load_files()
            else:
                messagebox.showerror("错误", f"删除文件失败: {response.status_code} - {response.text}")
        except Exception as e:
            messagebox.showerror("错误", f"删除文件失败: {str(e)}")
    
    def download_file(self):
        """下载文件到本地"""
        if not self.current_file_path:
            messagebox.showwarning("警告", "请先选择一个文件")
            return
        
        # 选择保存位置
        filename = os.path.basename(self.current_file_path)
        file_path = filedialog.asksaveasfilename(
            initialfile=filename,
            defaultextension=os.path.splitext(filename)[1],
            filetypes=[("所有文件", "*.*")]
        )
        
        if not file_path:
            return
        
        try:
            content = self.file_text.get(1.0, tk.END)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            messagebox.showinfo("成功", f"文件已下载到: {file_path}")
            self.status_label.config(text=f"已下载: {file_path}")
        except Exception as e:
            messagebox.showerror("错误", f"下载文件失败: {str(e)}")
    
    def upload_file(self):
        """上传本地文件"""
        if not self.repo:
            messagebox.showwarning("警告", "请先连接到仓库")
            return
        
        # 选择文件
        file_path = filedialog.askopenfilename(filetypes=[("所有文件", "*.*")])
        if not file_path:
            return
        
        # 创建上传对话框
        dialog = tk.Toplevel(self.root)
        dialog.title("上传文件")
        dialog.geometry("400x200")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 文件路径
        ttk.Label(dialog, text="本地文件:").pack(anchor=tk.W, pady=(10, 5))
        local_path_label = ttk.Label(dialog, text=file_path, wraplength=350)
        local_path_label.pack(fill=tk.X, pady=(0, 10))
        
        # 仓库路径
        ttk.Label(dialog, text="仓库路径 (可选):").pack(anchor=tk.W, pady=(10, 5))
        repo_path_entry = ttk.Entry(dialog, width=50)
        repo_path_entry.pack(fill=tk.X, pady=(0, 10))
        
        # 使用原文件名作为默认路径
        default_path = os.path.basename(file_path)
        repo_path_entry.insert(0, default_path)
        
        def upload():
            repo_path = repo_path_entry.get().strip() or default_path
            
            try:
                # 读取文件内容
                with open(file_path, 'rb') as f:
                    content = f.read()
                
                # 编码内容
                encoded_content = base64.b64encode(content).decode('utf-8')
                
                # 准备提交数据
                commit_data = {
                    "message": f"上传文件 {repo_path}",
                    "content": encoded_content,
                    "branch": self.current_branch
                }
                
                response = requests.put(
                    f"https://api.github.com/repos/{self.repo}/contents/{repo_path}",
                    headers=self.headers,
                    json=commit_data
                )
                
                if response.status_code in [200, 201]:
                    messagebox.showinfo("成功", f"文件已上传: {repo_path}")
                    dialog.destroy()
                    self.load_files()
                else:
                    messagebox.showerror("错误", f"上传文件失败: {response.status_code} - {response.text}")
            except Exception as e:
                messagebox.showerror("错误", f"上传文件失败: {str(e)}")
        
        # 按钮
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(btn_frame, text="上传", command=upload).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(btn_frame, text="取消", command=dialog.destroy).pack(side=tk.RIGHT)
    
    def refresh_files(self):
        """刷新文件列表"""
        self.load_files()
        self.status_label.config(text="文件列表已刷新")
    
    def on_search_change(self, event):
        """搜索框内容变化时"""
        search_text = self.search_entry.get().strip()
        if search_text:
            self.search_files()
        else:
            self.clear_search()
    
    def search_files(self):
        """搜索文件"""
        search_text = self.search_entry.get().strip().lower()
        if not search_text:
            return
        
        # 获取所有文件项
        all_items = []
        for item in self.file_tree.get_children():
            all_items.append(item)
        
        # 清空当前显示
        for item in self.file_tree.get_children():
            self.file_tree.delete(item)
        
        # 重新添加匹配的文件
        filtered_items = []
        for item in all_items:
            item_text = self.file_tree.item(item)['text']
            if search_text in item_text.lower():
                file_path = self.file_tree.item(item)['values'][0]
                file_type = self.file_tree.item(item)['values'][1]
                icon = self.get_file_icon(os.path.splitext(file_path)[1].lower())
                self.file_tree.insert('', 'end', text=f"{icon} {os.path.basename(file_path)}", 
                                    values=(file_path, file_type))
        
        self.status_label.config(text=f"找到 {len(self.file_tree.get_children())} 个匹配文件")
    
    def clear_search(self):
        """清除搜索"""
        self.search_entry.delete(0, tk.END)
        self.load_files()
        self.status_label.config(text="搜索已清除")
    
    def switch_preview_mode(self):
        """切换预览模式"""
        if not self.current_file_path:
            return
        
        mode = self.preview_mode.get()
        if mode == "preview":
            self.update_preview()
        
        # 切换到对应的标签页
        if self.current_file_path:
            ext = os.path.splitext(self.current_file_path)[1].lower()
            if PIL_AVAILABLE and ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp']:
                self.content_notebook.select(2)  # 图片预览
            else:
                if mode == "edit":
                    self.content_notebook.select(0)  # 文本编辑
                else:
                    self.content_notebook.select(1)  # 文件预览
    
    def update_preview(self):
        """更新预览内容"""
        if not self.current_file_path:
            return
        
        ext = os.path.splitext(self.current_file_path)[1].lower()
        content = self.file_text.get(1.0, tk.END)
        
        # 根据文件类型进行不同的预览处理
        if ext == '.md':
            # Markdown预览
            if MARKDOWN_AVAILABLE:
                try:
                    html_content = markdown.markdown(content)
                    self.preview_text.config(state=tk.NORMAL)
                    self.preview_text.delete(1.0, tk.END)
                    self.preview_text.insert(1.0, html_content)
                    self.preview_text.config(state=tk.DISABLED)
                except Exception as e:
                    self.preview_text.config(state=tk.NORMAL)
                    self.preview_text.delete(1.0, tk.END)
                    self.preview_text.insert(1.0, f"Markdown预览错误: {str(e)}")
                    self.preview_text.config(state=tk.DISABLED)
            else:
                # Markdown库不可用，显示原始文本
                self.preview_text.config(state=tk.NORMAL)
                self.preview_text.delete(1.0, tk.END)
                self.preview_text.insert(1.0, f"Markdown预览需要安装markdown库\n\n原始内容:\n{content}")
                self.preview_text.config(state=tk.DISABLED)
        elif ext in ['.py', '.js', '.html', '.css', '.json', '.xml', '.yml', '.yaml']:
            # 代码高亮预览（简化版）
            self.preview_text.config(state=tk.NORMAL)
            self.preview_text.delete(1.0, tk.END)
            # 简单的语法高亮模拟
            highlighted = self.simple_syntax_highlight(content, ext)
            self.preview_text.insert(1.0, highlighted)
            self.preview_text.config(state=tk.DISABLED)
        else:
            # 普通文本预览
            self.preview_text.config(state=tk.NORMAL)
            self.preview_text.delete(1.0, tk.END)
            self.preview_text.insert(1.0, content)
            self.preview_text.config(state=tk.DISABLED)
    
    def simple_syntax_highlight(self, content, ext):
        """简单的语法高亮"""
        # 这是一个简化的语法高亮实现
        # 在实际应用中，可以使用pygments等库
        lines = content.split('\n')
        highlighted_lines = []
        
        for line in lines:
            # 简单的关键词高亮
            if ext == '.py':
                # Python关键词
                keywords = ['def', 'class', 'import', 'from', 'if', 'else', 'elif', 'for', 'while', 'try', 'except', 'finally', 'return', 'yield', 'lambda', 'and', 'or', 'not', 'in', 'is']
                for keyword in keywords:
                    line = line.replace(keyword, f"【{keyword}】")
            elif ext == '.js':
                # JavaScript关键词
                keywords = ['function', 'var', 'let', 'const', 'if', 'else', 'for', 'while', 'try', 'catch', 'finally', 'return', 'class', 'extends', 'import', 'export', 'default']
                for keyword in keywords:
                    line = line.replace(keyword, f"【{keyword}】")
            
            highlighted_lines.append(line)
        
        return '\n'.join(highlighted_lines)
    
    def load_file_content(self, file_path):
        """加载文件内容（增强版）"""
        try:
            response = requests.get(
                f"https://api.github.com/repos/{self.repo}/contents/{file_path}",
                headers=self.headers,
                params={"ref": self.current_branch}
            )
            
            if response.status_code == 200:
                file_data = response.json()
                content = base64.b64decode(file_data['content']).decode('utf-8')
                
                self.current_file_path = file_path
                self.current_file_content = content
                self.current_file_sha = file_data['sha']
                
                self.file_path_label.config(text=f"文件: {file_path}")
                self.file_text.delete(1.0, tk.END)
                self.file_text.insert(1.0, content)
                
                # 根据文件类型设置预览
                ext = os.path.splitext(file_path)[1].lower()
                if PIL_AVAILABLE and ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp']:
                    # 图片文件
                    self.load_image_preview(file_data['content'])
                    self.content_notebook.select(2)  # 切换到图片预览
                else:
                    # 文本文件
                    self.update_preview()
                    if self.preview_mode.get() == "preview":
                        self.content_notebook.select(1)  # 切换到预览
                    else:
                        self.content_notebook.select(0)  # 切换到编辑
                
                self.status_label.config(text=f"已加载: {file_path}")
                
                # 加载提交历史
                self.load_file_commit_history(file_path)
                
            else:
                messagebox.showerror("错误", f"加载文件失败: {response.status_code}")
        except Exception as e:
            messagebox.showerror("错误", f"加载文件失败: {str(e)}")
    
    def load_image_preview(self, base64_content):
        """加载图片预览"""
        if not PIL_AVAILABLE or not BYTES_IO_AVAILABLE:
            self.image_label.config(image="", text="图片预览需要安装PIL库")
            return
        
        try:
            # 解码base64图片
            image_data = base64.b64decode(base64_content)
            image = Image.open(BytesIO(image_data))
            
            # 调整图片大小以适应界面
            max_width = 500
            max_height = 400
            image.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
            
            # 转换为PhotoImage
            photo = ImageTk.PhotoImage(image)
            
            # 更新图片标签
            self.image_label.config(image=photo, text="")
            self.image_label.image = photo  # 保持引用
            
        except Exception as e:
            self.image_label.config(image="", text=f"图片预览失败: {str(e)}")
            if hasattr(self.image_label, 'image'):
                delattr(self.image_label, 'image')
    
    def view_on_github(self):
        """在GitHub中查看文件"""
        if not self.current_file_path:
            messagebox.showwarning("警告", "请先选择一个文件")
            return
        
        # 构建GitHub文件URL
        github_url = f"https://github.com/{self.repo}/blob/{self.current_branch}/{self.current_file_path}"
        webbrowser.open(github_url)
        self.status_label.config(text=f"已在浏览器中打开: {github_url}")
    
    def load_commit_history(self):
        """加载提交历史"""
        if not self.repo:
            return
        
        try:
            # 获取提交历史
            response = requests.get(
                f"https://api.github.com/repos/{self.repo}/commits",
                headers=self.headers,
                params={"sha": self.current_branch, "per_page": 20}
            )
            
            if response.status_code == 200:
                commits = response.json()
                
                # 清空历史树
                for item in self.history_tree.get_children():
                    self.history_tree.delete(item)
                
                # 添加提交记录
                for commit in commits:
                    commit_info = commit['commit']
                    author = commit_info['author']['name']
                    message = commit_info['message'].split('\n')[0]  # 只取第一行
                    date = commit_info['author']['date'][:10]  # 只取日期部分
                    sha = commit['sha'][:7]  # 短SHA
                    
                    display_text = f"{message} - {author} ({date})"
                    self.history_tree.insert('', 'end', text=display_text, values=(sha, commit['sha']))
                
                self.status_label.config(text=f"已加载 {len(commits)} 条提交历史")
            else:
                messagebox.showerror("错误", f"加载提交历史失败: {response.status_code}")
        except Exception as e:
            messagebox.showerror("错误", f"加载提交历史失败: {str(e)}")
    
    def load_file_commit_history(self, file_path):
        """加载特定文件的提交历史"""
        if not self.repo:
            return
        
        try:
            # 获取特定文件的提交历史
            response = requests.get(
                f"https://api.github.com/repos/{self.repo}/commits",
                headers=self.headers,
                params={"sha": self.current_branch, "path": file_path, "per_page": 10}
            )
            
            if response.status_code == 200:
                commits = response.json()
                
                # 清空历史树
                for item in self.history_tree.get_children():
                    self.history_tree.delete(item)
                
                # 添加提交记录
                for commit in commits:
                    commit_info = commit['commit']
                    author = commit_info['author']['name']
                    message = commit_info['message'].split('\n')[0]
                    date = commit_info['author']['date'][:10]
                    sha = commit['sha'][:7]
                    
                    display_text = f"{message} - {author} ({date})"
                    self.history_tree.insert('', 'end', text=display_text, values=(sha, commit['sha']))
                
                self.status_label.config(text=f"已加载文件 '{file_path}' 的 {len(commits)} 条提交历史")
        except Exception as e:
            print(f"加载文件提交历史失败: {str(e)}")
    
    def on_history_select(self, event):
        """提交历史选择事件"""
        selection = self.history_tree.selection()
        if not selection:
            return
        
        item = self.history_tree.item(selection[0])
        commit_sha = item['values'][1] if item['values'] else ''
        
        if commit_sha:
            # 可以在新窗口中显示提交的详细信息
            self.show_commit_details(commit_sha)
    
    def show_commit_details(self, commit_sha):
        """显示提交详细信息"""
        try:
            response = requests.get(
                f"https://api.github.com/repos/{self.repo}/commits/{commit_sha}",
                headers=self.headers
            )
            
            if response.status_code == 200:
                commit_data = response.json()
                commit_info = commit_data['commit']
                
                # 创建详细信息窗口
                details_window = tk.Toplevel(self.root)
                details_window.title(f"提交详情 - {commit_sha[:7]}")
                details_window.geometry("600x400")
                details_window.transient(self.root)
                
                # 提交信息
                info_frame = ttk.LabelFrame(details_window, text="提交信息", padding="10")
                info_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
                
                # 作者
                author_text = f"作者: {commit_info['author']['name']} <{commit_info['author']['email']}>"
                ttk.Label(info_frame, text=author_text).pack(anchor=tk.W, pady=(0, 5))
                
                # 日期
                date_text = f"日期: {commit_info['author']['date']}"
                ttk.Label(info_frame, text=date_text).pack(anchor=tk.W, pady=(0, 5))
                
                # SHA
                sha_text = f"SHA: {commit_data['sha']}"
                ttk.Label(info_frame, text=sha_text).pack(anchor=tk.W, pady=(0, 10))
                
                # 提交消息
                ttk.Label(info_frame, text="提交消息:").pack(anchor=tk.W, pady=(0, 5))
                message_text = tk.Text(info_frame, width=70, height=8, wrap=tk.WORD)
                message_text.pack(fill=tk.BOTH, expand=True)
                message_text.insert(1.0, commit_info['message'])
                message_text.config(state=tk.DISABLED)
                
                # 文件变更
                if 'files' in commit_data:
                    files_frame = ttk.LabelFrame(details_window, text="文件变更", padding="10")
                    files_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
                    
                    files_text = tk.Text(files_frame, width=70, height=10, wrap=tk.NONE)
                    files_text.pack(fill=tk.BOTH, expand=True)
                    
                    for file in commit_data['files']:
                        change_type = file['status']
                        filename = file['filename']
                        additions = file.get('additions', 0)
                        deletions = file.get('deletions', 0)
                        
                        file_text = f"[{change_type}] {filename} (+{additions} -{deletions})"
                        files_text.insert(tk.END, file_text + '\n')
                    
                    files_text.config(state=tk.DISABLED)
                
                # 关闭按钮
                ttk.Button(details_window, text="关闭", command=details_window.destroy).pack(pady=10)
                
        except Exception as e:
            messagebox.showerror("错误", f"获取提交详情失败: {str(e)}")
    
    def create_branch(self):
        """创建新分支"""
        if not self.repo:
            messagebox.showwarning("警告", "请先连接到仓库")
            return
        
        # 创建对话框
        dialog = tk.Toplevel(self.root)
        dialog.title("创建新分支")
        dialog.geometry("400x200")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 分支名称
        ttk.Label(dialog, text="新分支名称:").pack(anchor=tk.W, pady=(10, 5))
        branch_name_entry = ttk.Entry(dialog, width=40)
        branch_name_entry.pack(fill=tk.X, pady=(0, 10))
        
        # 基于哪个分支
        ttk.Label(dialog, text="基于分支:").pack(anchor=tk.W, pady=(10, 5))
        base_branch_combo = ttk.Combobox(dialog, width=37, state="readonly")
        base_branch_combo['values'] = self.branch_combo['values']
        if self.branch_combo['values']:
            base_branch_combo.set(self.branch_combo['values'][0])
        base_branch_combo.pack(fill=tk.X, pady=(0, 10))
        
        def create():
            new_branch_name = branch_name_entry.get().strip()
            base_branch = base_branch_combo.get()
            
            if not new_branch_name:
                messagebox.showwarning("警告", "请输入分支名称")
                return
            
            try:
                # 获取基础分支的最新提交
                response = requests.get(
                    f"https://api.github.com/repos/{self.repo}/git/refs/heads/{base_branch}",
                    headers=self.headers
                )
                
                if response.status_code == 200:
                    ref_data = response.json()
                    sha = ref_data['object']['sha']
                    
                    # 创建新分支
                    create_data = {
                        "ref": f"refs/heads/{new_branch_name}",
                        "sha": sha
                    }
                    
                    response = requests.post(
                        f"https://api.github.com/repos/{self.repo}/git/refs",
                        headers=self.headers,
                        json=create_data
                    )
                    
                    if response.status_code == 201:
                        messagebox.showinfo("成功", f"分支 '{new_branch_name}' 已创建")
                        dialog.destroy()
                        self.load_branches()  # 刷新分支列表
                    else:
                        messagebox.showerror("错误", f"创建分支失败: {response.status_code} - {response.text}")
                else:
                    messagebox.showerror("错误", f"获取基础分支信息失败: {response.status_code}")
                    
            except Exception as e:
                messagebox.showerror("错误", f"创建分支失败: {str(e)}")
        
        # 按钮
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(btn_frame, text="创建", command=create).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(btn_frame, text="取消", command=dialog.destroy).pack(side=tk.RIGHT)

if __name__ == "__main__":
    root = tk.Tk()
    app = GitHubRepoManager(root)
    root.mainloop()