// worker.js with ID-based storage and retrieval
let db = null;

// Open connection once when worker starts
function openDatabase() {
  return new Promise((resolve, reject) => {
    if (db) {
      resolve(db);
      return;
    }
    
    const request = indexedDB.open("DashDB", 1);
    
    request.onupgradeneeded = function(event) {
      const db = event.target.result;
      if (!db.objectStoreNames.contains("dataStore")) {
        // Use auto-incrementing key if id is not provided
        const store = db.createObjectStore("dataStore", { 
          keyPath: "id", 
          autoIncrement: true 
        });
        
        // Create useful indices
        store.createIndex("timestamp", "timestamp", { unique: false });
        store.createIndex("category", "category", { unique: false });
        store.createIndex("name", "name", { unique: false });
      }
    };
    
    request.onsuccess = function(event) {
      db = event.target.result;
      db.onclose = () => { db = null; };
      db.onerror = (event) => { 
        console.error("Database error:", event.target.errorCode);
      };
      resolve(db);
    };
    
    request.onerror = function(event) {
      reject("IndexedDB error: " + event.target.errorCode);
    };
  });
}

// Initialize the database connection when the worker starts
openDatabase();

// Generate a UUID for use as ID if needed
function generateUUID() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
    const r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
}

// Store data with automatic ID assignment if not provided
async function storeData(data) {
  if (!db) await openDatabase();
  
  return new Promise((resolve, reject) => {
    const tx = db.transaction("dataStore", "readwrite");
    const store = tx.objectStore("dataStore");
    
    let results = [];
    
    if (Array.isArray(data)) {
      // Process array of items
      data.forEach(item => {
        // Ensure each item has an ID
        if (!item.id) {
          item.id = generateUUID();
        }
        
        // Add timestamp if not present
        if (!item.timestamp) {
          item.timestamp = Date.now();
        }
        
        const request = store.put(item);
        request.onsuccess = (event) => {
          results.push({
            id: event.target.result,
            success: true
          });
        };
      });
    } else {
      // Process single item
      if (!data.id) {
        data.id = generateUUID();
      }
      
      if (!data.timestamp) {
        data.timestamp = Date.now();
      }
      
      const request = store.put(data);
      request.onsuccess = (event) => {
        results.push({
          id: event.target.result,
          success: true
        });
      };
    }
    
    tx.oncomplete = () => resolve({ 
      status: "complete", 
      count: results.length,
      results: results
    });
    
    tx.onerror = (event) => reject(event.target.error);
  });
}

// Retrieve data by ID
async function getDataById(id) {
  if (!db) await openDatabase();
  
  return new Promise((resolve, reject) => {
    const tx = db.transaction("dataStore", "readonly");
    const store = tx.objectStore("dataStore");
    const request = store.get(id);
    
    request.onsuccess = () => resolve(request.result);
    request.onerror = (event) => reject(event.target.error);
  });
}

// Retrieve multiple items by array of IDs
async function getDataByIds(ids) {
  if (!db) await openDatabase();
  
  return new Promise((resolve, reject) => {
    const tx = db.transaction("dataStore", "readonly");
    const store = tx.objectStore("dataStore");
    
    const results = [];
    let completed = 0;
    
    ids.forEach(id => {
      const request = store.get(id);
      request.onsuccess = () => {
        if (request.result) {
          results.push(request.result);
        }
        completed++;
        
        if (completed === ids.length) {
          resolve(results);
        }
      };
      request.onerror = (event) => {
        completed++;
        console.error(`Error retrieving ID ${id}: ${event.target.error}`);
        
        if (completed === ids.length) {
          resolve(results);
        }
      };
    });
    
    // Handle empty array case
    if (ids.length === 0) {
      resolve([]);
    }
  });
}

// Retrieve all data
async function getAllData() {
  if (!db) await openDatabase();
  
  return new Promise((resolve, reject) => {
    const tx = db.transaction("dataStore", "readonly");
    const store = tx.objectStore("dataStore");
    const request = store.getAll();
    
    request.onsuccess = () => resolve(request.result);
    request.onerror = (event) => reject(event.target.error);
  });
}

// Get all IDs in the database
async function getAllIds() {
  if (!db) await openDatabase();
  
  return new Promise((resolve, reject) => {
    const tx = db.transaction("dataStore", "readonly");
    const store = tx.objectStore("dataStore");
    const request = store.getAllKeys();
    
    request.onsuccess = () => resolve(request.result);
    request.onerror = (event) => reject(event.target.error);
  });
}

// Update specific fields of an existing item by ID
async function updateDataById(id, updates) {
  if (!db) await openDatabase();
  
  return new Promise((resolve, reject) => {
    const tx = db.transaction("dataStore", "readwrite");
    const store = tx.objectStore("dataStore");
    
    // First get the existing item
    const getRequest = store.get(id);
    
    getRequest.onsuccess = () => {
      const item = getRequest.result;
      if (!item) {
        reject(`Item with ID ${id} not found`);
        return;
      }
      
      // Apply updates to the item
      Object.assign(item, updates);
      
      // Update the modified timestamp
      item.lastModified = Date.now();
      
      // Put the updated item back
      const updateRequest = store.put(item);
      
      updateRequest.onsuccess = () => {
        resolve({
          status: "complete",
          message: `Item ${id} updated successfully`,
          id: id
        });
      };
      
      updateRequest.onerror = (event) => {
        reject(event.target.error);
      };
    };
    
    getRequest.onerror = (event) => {
      reject(event.target.error);
    };
  });
}

// Delete data by ID
async function deleteDataById(id) {
  if (!db) await openDatabase();
  
  return new Promise((resolve, reject) => {
    const tx = db.transaction("dataStore", "readwrite");
    const store = tx.objectStore("dataStore");
    const request = store.delete(id);
    
    request.onsuccess = () => resolve({ 
      status: "complete", 
      message: `Item ${id} deleted`,
      id: id
    });
    request.onerror = (event) => reject(event.target.error);
  });
}

// Delete multiple items by array of IDs
async function deleteDataByIds(ids) {
  if (!db) await openDatabase();
  
  return new Promise((resolve, reject) => {
    const tx = db.transaction("dataStore", "readwrite");
    const store = tx.objectStore("dataStore");
    
    const results = [];
    let completed = 0;
    
    ids.forEach(id => {
      const request = store.delete(id);
      request.onsuccess = () => {
        results.push({
          id: id,
          deleted: true
        });
        completed++;
        
        if (completed === ids.length) {
          resolve({
            status: "complete",
            count: results.length,
            results: results
          });
        }
      };
      request.onerror = (event) => {
        results.push({
          id: id,
          deleted: false,
          error: event.target.error.toString()
        });
        completed++;
        
        if (completed === ids.length) {
          resolve({
            status: "complete",
            count: results.filter(r => r.deleted).length,
            results: results
          });
        }
      };
    });
    
    // Handle empty array case
    if (ids.length === 0) {
      resolve({
        status: "complete",
        count: 0,
        results: []
      });
    }
  });
}

// Handle messages from the main thread
self.onmessage = async function(e) {
  try {
    const { action, payload } = e.data;
    let result;
    
    switch (action) {
      case "store":
        result = await storeData(payload);
        break;
      case "getById":
        result = await getDataById(payload);
        break;
      case "getByIds":
        result = await getDataByIds(payload);
        break;
      case "getAll":
        result = await getAllData();
        break;
      case "getAllIds":
        result = await getAllIds();
        break;
      case "update":
        result = await updateDataById(payload.id, payload.updates);
        break;
      case "delete":
        result = await deleteDataById(payload);
        break;
      case "deleteMultiple":
        result = await deleteDataByIds(payload);
        break;
      default:
        throw new Error(`Unknown action: ${action}`);
    }
    
    self.postMessage({
      status: "success",
      action: action,
      result: result
    });
  } catch (error) {
    self.postMessage({
      status: "error", 
      action: e.data.action,
      message: error.toString()
    });
  }
};