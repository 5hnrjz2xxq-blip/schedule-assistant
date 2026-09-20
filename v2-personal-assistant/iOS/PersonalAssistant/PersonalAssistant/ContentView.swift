import SwiftUI
import WebKit
import UIKit

// MARK: - Main Content View

struct ContentView: View {
    @State private var extractionState: ExtractionState = .idle
    @State private var parsedCourses: [ParsedCourse] = []
    @State private var showingAlert = false
    @State private var alertTitle = ""
    @State private var alertMessage = ""
    @State private var showingShareSheet = false
    @State private var exportedFileURL: URL?
    
    var body: some View {
        NavigationView {
            VStack(spacing: 0) {
                // WebView
                WebViewRepresentable(
                    extractionState: $extractionState,
                    parsedCourses: $parsedCourses
                )
                .ignoresSafeArea(edges: .bottom)
                
                // Schedule List (shown after extraction)
                if case .parsed(let courses) = extractionState {
                    ScheduleListView(courses: courses)
                        .frame(height: 200)
                }
            }
            .navigationTitle("宜宾学院课程表")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("刷新") {
                        extractionState = .idle
                    }
                }
                
                ToolbarItem(placement: .navigationBarTrailing) {
                    HStack {
                        // Extract Schedule Button
                        Button(action: extractSchedule) {
                            HStack {
                                Image(systemName: "doc.text.magnifyingglass")
                                Text("提取课程")
                            }
                        }
                        .disabled(extractionState == .extracting || extractionState == .exporting)
                        
                        // Export ICS Button
                        if case .parsed(let courses) = extractionState {
                            Button(action: exportICS) {
                                HStack {
                                    Image(systemName: "calendar.badge.plus")
                                    Text("导出日历")
                                }
                            }
                            .disabled(extractionState == .exporting)
                        }
                    }
                }
            }
            .overlay {
                if extractionState == .extracting {
                    ProgressView("正在提取课程数据...")
                        .padding()
                        .background(.ultraThinMaterial)
                        .cornerRadius(10)
                }
                
                if case .exporting = extractionState {
                    ProgressView("正在导出日历文件...")
                        .padding()
                        .background(.ultraThinMaterial)
                        .cornerRadius(10)
                }
            }
            .alert(alertTitle, isPresented: $showingAlert) {
                Button("确定", role: .cancel) {}
            } message: {
                Text(alertMessage)
            }
            .sheet(isPresented: $showingShareSheet) {
                if let url = exportedFileURL {
                    ShareSheet(items: [url])
                }
            }
        }
    }
    
    // MARK: - Actions
    
    private func extractSchedule() {
        extractionState = .extracting
        
        // Post notification to WebView to start extraction
        NotificationCenter.default.post(name: .startExtraction, object: nil)
        
        // Set timeout
        DispatchQueue.main.asyncAfter(deadline: .now() + 30) {
            if case .extracting = extractionState {
                showError(title: "提取超时", message: "无法提取课程数据，请确保已登录并加载了课程表页面")
                extractionState = .idle
            }
        }
    }
    
    private func exportICS() {
        guard !parsedCourses.isEmpty else {
            showError(title: "无课程数据", message: "请先提取课程数据")
            return
        }
        
        extractionState = .exporting
        
        DispatchQueue.global(qos: .userInitiated).async {
            let icsContent = ICSGenerator.generateICS(from: parsedCourses)
            
            DispatchQueue.main.async {
                if let fileURL = ICSGenerator.saveICS(icsContent) {
                    exportedFileURL = fileURL
                    extractionState = .exported(fileURL)
                    showingShareSheet = true
                } else {
                    showError(title: "导出失败", message: "无法保存日历文件")
                    extractionState = .parsed(parsedCourses)
                }
            }
        }
    }
    
    private func showError(title: String, message: String) {
        alertTitle = title
        alertMessage = message
        showingAlert = true
    }
}

// MARK: - Schedule List View

struct ScheduleListView: View {
    let courses: [ParsedCourse]
    
    var body: some View {
        List {
            Section(header: Text("已提取的课程 (\(courses.count)门)")) {
                ForEach(courses) { course in
                    VStack(alignment: .leading, spacing: 4) {
                        Text(course.courseName)
                            .font(.headline)
                        
                        HStack {
                            Text(course.teacher)
                                .font(.subheadline)
                                .foregroundColor(.secondary)
                            
                            Text("•")
                                .foregroundColor(.secondary)
                            
                            Text(course.location)
                                .font(.subheadline)
                                .foregroundColor(.secondary)
                        }
                        
                        HStack {
                            Text(dayOfWeekString(course.dayOfWeek))
                                .font(.caption)
                                .padding(.horizontal, 6)
                                .padding(.vertical, 2)
                                .background(Color.blue.opacity(0.1))
                                .cornerRadius(4)
                            
                            Text(course.timeSlot)
                                .font(.caption)
                                .padding(.horizontal, 6)
                                .padding(.vertical, 2)
                                .background(Color.green.opacity(0.1))
                                .cornerRadius(4)
                            
                            Text(course.weekSpec)
                                .font(.caption)
                                .padding(.horizontal, 6)
                                .padding(.vertical, 2)
                                .background(Color.orange.opacity(0.1))
                                .cornerRadius(4)
                        }
                    }
                    .padding(.vertical, 4)
                }
            }
        }
        .listStyle(.plain)
    }
    
    private func dayOfWeekString(_ day: Int) -> String {
        switch day {
        case 1: return "星期一"
        case 2: return "星期二"
        case 3: return "星期三"
        case 4: return "星期四"
        case 5: return "星期五"
        case 6: return "星期六"
        case 7: return "星期日"
        default: return "未知"
        }
    }
}

// MARK: - WebView Representable

struct WebViewRepresentable: UIViewRepresentable {
    @Binding var extractionState: ExtractionState
    @Binding var parsedCourses: [ParsedCourse]
    
    func makeCoordinator() -> Coordinator {
        Coordinator(self)
    }
    
    func makeUIView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        config.allowsInlineMediaPlayback = true
        
        let webView = WKWebView(frame: .zero, configuration: config)
        webView.navigationDelegate = context.coordinator
        webView.uiDelegate = context.coordinator
        
        // Load login page
        let url = URL(string: "https://ehall.yibinu.edu.cn/authserver/login")!
        webView.load(URLRequest(url: url))
        
        // Register for extraction notification
        NotificationCenter.default.addObserver(
            forName: .startExtraction,
            object: nil,
            queue: .main
        ) { _ in
            context.coordinator.extractSchedule(from: webView)
        }
        
        return webView
    }
    
    func updateUIView(_ uiView: WKWebView, context: Context) {
        // No updates needed
    }
    
    class Coordinator: NSObject, WKNavigationDelegate, WKUIDelegate {
        var parent: WebViewRepresentable
        
        init(_ parent: WebViewRepresentable) {
            self.parent = parent
        }
        
        // MARK: - Navigation Delegate
        
        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            let currentURL = webView.url?.absoluteString ?? ""
            
            // Check if we're on the schedule page
            if currentURL.contains("xskcb") {
                parent.extractionState = .waitingForData
                
                // Wait for table to load
                DispatchQueue.main.asyncAfter(deadline: .now() + 10) {
                    self.extractSchedule(from: webView)
                }
            } else if currentURL.contains("authserver/login") {
                parent.extractionState = .loggingIn
            }
        }
        
        func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
            decisionHandler(.allow)
        }
        
        // MARK: - Extraction
        
        func extractSchedule(from webView: WKWebView) {
            let jsCode = """
            (function(){
                var courses = [];
                var table = document.querySelector('table');
                if(!table) return JSON.stringify([]);
                var rows = table.querySelectorAll('tr');
                var ps=0, pe=0;
                rows.forEach(function(row){
                    var cells = row.querySelectorAll('td');
                    var ci=0;
                    cells.forEach(function(cell){
                        var text = cell.textContent.trim();
                        var colspan = parseInt(cell.getAttribute('colspan')||'1');
                        var rowspan = parseInt(cell.getAttribute('rowspan')||'1');
                        if(/^\\d{1,2}$/.test(text) && parseInt(text)<=12 && ci<=1){
                            ps=parseInt(text); pe=ps+rowspan-1;
                        } else if(text.length>15){
                            courses.push({full:text,period_start:ps,period_end:pe,day:ci-1});
                        }
                        ci+=colspan;
                    });
                });
                return JSON.stringify(courses);
            })()
            """
            
            webView.evaluateJavaScript(jsCode) { result, error in
                DispatchQueue.main.async {
                    if let error = error {
                        self.parent.extractionState = .error("JavaScript执行失败: \(error.localizedDescription)")
                        return
                    }
                    
                    guard let jsonString = result as? String,
                          let jsonData = jsonString.data(using: .utf8) else {
                        self.parent.extractionState = .error("无法解析提取结果")
                        return
                    }
                    
                    do {
                        let decoder = JSONDecoder()
                        let rawEntries = try decoder.decode([RawCourseEntry].self, from: jsonData)
                        
                        if rawEntries.isEmpty {
                            self.parent.extractionState = .error("未找到课程数据，请确保已登录并加载了课程表")
                            return
                        }
                        
                        let courses = ScheduleExtractor.parseCourses(from: rawEntries)
                        self.parent.parsedCourses = courses
                        self.parent.extractionState = .parsed(courses)
                        
                    } catch {
                        self.parent.extractionState = .error("数据解析失败: \(error.localizedDescription)")
                    }
                }
            }
        }
        
        // MARK: - Alert Handling
        
        func webView(_ webView: WKWebView, runJavaScriptAlertPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping () -> Void) {
            completionHandler()
        }
        
        func webView(_ webView: WKWebView, runJavaScriptConfirmPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (Bool) -> Void) {
            completionHandler(true)
        }
    }
}

// MARK: - Share Sheet

struct ShareSheet: UIViewControllerRepresentable {
    let items: [Any]
    
    func makeUIViewController(context: Context) -> UIActivityViewController {
        UIActivityViewController(activityItems: items, applicationActivities: nil)
    }
    
    func updateUIViewController(_ uiViewController: UIActivityViewController, context: Context) {}
}

// MARK: - Notification Names

extension Notification.Name {
    static let startExtraction = Notification.Name("startExtraction")
}

// MARK: - Preview

struct ContentView_Previews: PreviewProvider {
    static var previews: some View {
        ContentView()
    }
}
