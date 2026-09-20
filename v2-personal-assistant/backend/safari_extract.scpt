-- 自动从 Safari 提取课表数据
-- 前提：用户已在 Safari 登录教务系统

on run
    tell application "Safari"
        activate
    end tell
    
    -- 导航到课表页面
    tell application "Safari"
        set URL of front document to "https://ehall.yibinu.edu.cn/jwapp/sys/wdkb/*default/index.do#/xskcb"
    end tell
    
    -- 等待页面加载
    delay 8
    
    -- 提取课表数据
    tell application "Safari"
        set jsCode to "
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
        "
        set result to do JavaScript jsCode in document 1
    end tell
    
    return result
end run
