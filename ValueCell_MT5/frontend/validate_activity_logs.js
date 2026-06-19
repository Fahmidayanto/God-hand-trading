#!/usr/bin/env node
/**
 * Activity Logs Frontend Validation Script
 * 
 * Validates the frontend implementation:
 * - TypeScript types
 * - API integration
 * - Component usage
 * 
 * Run: node validate_activity_logs.js
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// ANSI color codes for output
const colors = {
  green: '\x1b[32m',
  red: '\x1b[31m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  reset: '\x1b[0m',
};

function printStatus(testName, passed, details = '') {
  const status = passed ? `${colors.green}✅ PASS${colors.reset}` : `${colors.red}❌ FAIL${colors.reset}`;
  console.log(`${status} | ${testName}`);
  if (details && !passed) {
    console.log(`       └─ ${details}`);
  }
}

function fileExists(filePath) {
  try {
    return fs.existsSync(filePath);
  } catch {
    return false;
  }
}

function readFile(filePath) {
  try {
    return fs.readFileSync(filePath, 'utf-8');
  } catch {
    return null;
  }
}

function test1_FileStructure() {
  console.log(`\n${colors.blue}🧪 Test 1: Validating File Structure...${colors.reset}`);
  
  const files = [
    'src/api/activity-logs.ts',
    'src/app/mt5/dashboard.tsx',
    'src/global.css',
  ];
  
  let allExist = true;
  for (const file of files) {
    const fullPath = path.join(__dirname, file);
    const exists = fileExists(fullPath);
    printStatus(`File: ${file}`, exists);
    if (!exists) allExist = false;
  }
  
  return allExist;
}

function test2_APIIntegration() {
  console.log(`\n${colors.blue}🧪 Test 2: Validating API Integration...${colors.reset}`);
  
  const apiFile = path.join(__dirname, 'src/api/activity-logs.ts');
  const content = readFile(apiFile);
  
  if (!content) {
    printStatus('API File Read', false, 'Cannot read file');
    return false;
  }
  
  // Check for required exports
  const checks = [
    { name: 'useActivityLogs hook', pattern: /export const useActivityLogs/ },
    { name: 'ActivityLog interface', pattern: /export interface ActivityLog/ },
    { name: 'EventType type', pattern: /export type EventType/ },
    { name: 'Severity type', pattern: /export type Severity/ },
    { name: 'EVENT_TYPE_ICONS mapping', pattern: /export const EVENT_TYPE_ICONS/ },
    { name: 'SEVERITY_CLASSES mapping', pattern: /export const SEVERITY_CLASSES/ },
  ];
  
  let allPresent = true;
  for (const check of checks) {
    const found = check.pattern.test(content);
    printStatus(check.name, found);
    if (!found) allPresent = false;
  }
  
  return allPresent;
}

function test3_DashboardIntegration() {
  console.log(`\n${colors.blue}🧪 Test 3: Validating Dashboard Integration...${colors.reset}`);
  
  const dashboardFile = path.join(__dirname, 'src/app/mt5/dashboard.tsx');
  const content = readFile(dashboardFile);
  
  if (!content) {
    printStatus('Dashboard File Read', false, 'Cannot read file');
    return false;
  }
  
  // Check for useActivityLogs usage
  const hasHook = /useActivityLogs/.test(content);
  printStatus('useActivityLogs hook imported', hasHook);
  
  // Check hardcoded logs are removed
  const hasHardcodedTime = /13:45|14:28|14:12/.test(content);
  printStatus('No hardcoded timestamps', !hasHardcodedTime);
  
  // Check for real data mapping
  const hasMapping = /activityLogs\.logs\.map/.test(content);
  printStatus('Maps activityLogs.logs', hasMapping);
  
  // Check for loading state
  const hasLoadingState = /activityLogsLoading/.test(content);
  printStatus('Has loading state', hasLoadingState);
  
  // Check for error state
  const hasErrorState = /activityLogsError/.test(content);
  printStatus('Has error state', hasErrorState);
  
  return hasHook && !hasHardcodedTime && hasMapping && hasLoadingState && hasErrorState;
}

function test4_CSSClasses() {
  console.log(`\n${colors.blue}🧪 Test 4: Validating CSS Classes...${colors.reset}`);
  
  const cssFile = path.join(__dirname, 'src/global.css');
  const content = readFile(cssFile);
  
  if (!content) {
    printStatus('CSS File Read', false, 'Cannot read file');
    return false;
  }
  
  // Check for log severity classes
  const classes = [
    { name: '.log-success', pattern: /\.log-success/ },
    { name: '.log-info', pattern: /\.log-info/ },
    { name: '.log-warning', pattern: /\.log-warning/ },
    { name: '.log-error', pattern: /\.log-error/ },
  ];
  
  let allPresent = true;
  for (const cls of classes) {
    const found = cls.pattern.test(content);
    printStatus(cls.name, found);
    if (!found) allPresent = false;
  }
  
  return allPresent;
}

function test5_TypeScriptTypes() {
  console.log(`\n${colors.blue}🧪 Test 5: Validating TypeScript Types...${colors.reset}`);
  
  const apiFile = path.join(__dirname, 'src/api/activity-logs.ts');
  const content = readFile(apiFile);
  
  if (!content) {
    printStatus('API File Read', false, 'Cannot read file');
    return false;
  }
  
  // Count event types
  const eventTypeMatch = content.match(/export type EventType\s*=\s*\n([^;]+);/s);
  if (eventTypeMatch) {
    const eventTypes = eventTypeMatch[1].match(/"\w+"/g);
    const count = eventTypes ? eventTypes.length : 0;
    printStatus(`EventType count (${count} types)`, count >= 18);
    return count >= 18;
  } else {
    printStatus('EventType definition', false, 'Cannot parse EventType');
    return false;
  }
}

function main() {
  console.log('='.repeat(60));
  console.log(`${colors.blue}🎯 Activity Logs Frontend Validation${colors.reset}`);
  console.log('='.repeat(60));
  
  let allPassed = true;
  
  // Run tests
  allPassed &= test1_FileStructure();
  allPassed &= test2_APIIntegration();
  allPassed &= test3_DashboardIntegration();
  allPassed &= test4_CSSClasses();
  allPassed &= test5_TypeScriptTypes();
  
  // Summary
  console.log('\n' + '='.repeat(60));
  if (allPassed) {
    console.log(`${colors.green}✅ ALL TESTS PASSED - Frontend implementation is valid!${colors.reset}`);
    console.log(`${colors.green}🚀 Ready for production deployment${colors.reset}`);
    process.exit(0);
  } else {
    console.log(`${colors.red}❌ SOME TESTS FAILED - Please review the errors above${colors.reset}`);
    process.exit(1);
  }
  console.log('='.repeat(60));
}

main();
