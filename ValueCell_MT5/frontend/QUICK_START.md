# Activity Logs System - Quick Start Guide

## 🚀 Get Started in 3 Steps

### Step 1: Start Backend Server
```bash
cd "d:\Project\Project MT5\AI_Trading_Server"
python -m api.server
```

**Expected Output:**
```
INFO:     Started server process
INFO:     Uvicorn running on http://localhost:8000
INFO:     Application startup complete
```

### Step 2: Start Frontend
```bash
cd "d:\Project\Project MT5\ValueCell_MT5\frontend"
npm run dev
```

**Expected Output:**
```
VITE v5.x.x ready in xxx ms

➜  Local:   http://localhost:5173/
➜  Network: use --host to expose
```

### Step 3: Open Dashboard
Open browser and navigate to:
```
http://localhost:5173/mt5/dashboard
```

## ✅ Verification Checklist

### Backend Running?
- [ ] Navigate to: `http://localhost:8000/api/v1/activity-logs`
- [ ] Should see JSON response with logs

### Frontend Running?
- [ ] Dashboard loads without errors
- [ ] Activity Logs section visible
- [ ] Logs are displayed (not "Loading...")
- [ ] No console errors (F12 → Console)

### Auto-Refresh Working?
- [ ] Open Network tab (F12 → Network)
- [ ] Filter by "activity-logs"
- [ ] Should see new request every 5 seconds

### Visual Check
- [ ] Log entries have icons (emojis)
- [ ] Timestamps show current time
- [ ] Colors match severity (blue/green/yellow/red)
- [ ] No hardcoded data visible

## 🐛 Troubleshooting

### Problem: "Loading activity logs..." stuck
**Solution:**
1. Check backend is running (Step 1)
2. Verify API endpoint: `http://localhost:8000/api/v1/activity-logs`
3. Check browser console for errors
4. Check Network tab for failed requests

### Problem: Console shows CORS error
**Solution:**
1. Backend must allow frontend origin
2. Check backend CORS configuration
3. Ensure ports match (backend: 8000, frontend: 5173)

### Problem: "Failed to Load Activity Logs"
**Solution:**
1. Backend might be down → Start backend (Step 1)
2. Network issue → Check internet connection
3. API endpoint wrong → Check VITE_API_BASE_URL in .env

### Problem: No logs showing (Empty state)
**Solution:**
1. Backend database might be empty
2. Check backend logs for errors
3. Verify API returns logs: `curl http://localhost:8000/api/v1/activity-logs`

### Problem: TypeScript errors
**Solution:**
```bash
cd frontend
npm run type-check
```

### Problem: Icons not displaying
**Solution:**
1. Font might not support emojis
2. Check CSS is loaded
3. Try different browser

## 📊 Testing Different States

### Test Loading State
1. Stop backend server
2. Refresh dashboard
3. Quickly observe "Loading activity logs..."
4. Then see error state

### Test Error State
1. Stop backend server
2. Wait for next refresh (5 seconds)
3. Should see "Failed to Load Activity Logs" with error icon

### Test Empty State
1. Clear all logs from backend
2. Refresh dashboard
3. Should see "No Activity Logs" message

### Test Success State
1. Ensure backend has logs
2. Refresh dashboard
3. Should see list of logs with icons and colors

## 🔍 Debugging Tools

### Browser Console
```javascript
// Check React Query cache
window.__REACT_QUERY_DEVTOOLS__

// Count log entries
console.log(document.querySelectorAll('.log-entry').length);

// Check API response
fetch('http://localhost:8000/api/v1/activity-logs?limit=10')
  .then(r => r.json())
  .then(console.log);
```

### Network Tab
1. Open DevTools (F12)
2. Go to Network tab
3. Filter by "activity-logs"
4. Click on request to see details
5. Check Response tab for JSON data

### React DevTools
1. Install React DevTools extension
2. Open DevTools → React
3. Find MT5Dashboard component
4. Check hooks → useActivityLogs
5. Verify data state

## 📝 Common Commands

### Backend
```bash
# Start server
python -m api.server

# Check logs endpoint
curl http://localhost:8000/api/v1/activity-logs

# Check with parameters
curl "http://localhost:8000/api/v1/activity-logs?limit=5&severity=ERROR"
```

### Frontend
```bash
# Start dev server
npm run dev

# Type check
npm run type-check

# Build for production
npm run build

# Preview production build
npm run preview
```

## 🎯 Success Indicators

### ✅ Everything Working When:
1. ✓ Backend running on port 8000
2. ✓ Frontend running on port 5173
3. ✓ Dashboard loads without errors
4. ✓ Activity logs section shows real data
5. ✓ Logs refresh every 5 seconds
6. ✓ Icons and colors display correctly
7. ✓ Timestamps show current time
8. ✓ No console errors
9. ✓ Network tab shows successful requests
10. ✓ React DevTools shows correct state

## 📚 Documentation

### Full Documentation
- `ACTIVITY_LOGS_IMPLEMENTATION.md` - Complete implementation guide
- `IMPLEMENTATION_SUMMARY.md` - Quick summary
- `ARCHITECTURE_DIAGRAM.md` - System architecture

### Code Files
- `src/api/activity-logs.ts` - API hook and types
- `src/app/mt5/dashboard.tsx` - Dashboard component
- `src/global.css` - Styling

## 🆘 Need Help?

### Check These First
1. Backend logs (terminal where you ran `python -m api.server`)
2. Frontend logs (terminal where you ran `npm run dev`)
3. Browser console (F12 → Console)
4. Network tab (F12 → Network)

### Common Issues
- **Port conflict**: Change port in backend or frontend config
- **Module not found**: Run `npm install` in frontend directory
- **API not found**: Check VITE_API_BASE_URL in frontend/.env
- **CORS error**: Configure CORS in backend

## 🎉 Next Steps

Once everything is working:
1. ✓ Test different event types
2. ✓ Test different severity levels
3. ✓ Monitor auto-refresh behavior
4. ✓ Test error handling (stop backend)
5. ✓ Test empty state (clear logs)
6. ✓ Performance testing (many logs)
7. ✓ Mobile responsiveness
8. ✓ Production build

## 📞 Support

If you encounter issues not covered here:
1. Check backend logs for errors
2. Check browser console for errors
3. Verify API endpoint returns correct data
4. Review implementation documentation
5. Check TypeScript types match API response

---

**Quick Start Status**: ✅ **READY**  
**Estimated Setup Time**: ⏱️ **< 5 minutes**  
**Difficulty Level**: 🟢 **EASY**

*Start backend → Start frontend → Open dashboard → Done!*
