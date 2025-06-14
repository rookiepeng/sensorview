/**
 * @fileoverview Web Worker implementation for IndexedDB storage and retrieval operations
 * This worker handles all database operations for the SensorView application, providing
 * an asynchronous interface for storing, retrieving, updating, and deleting sensor data.
 * 
 * @description
 * The worker implements the following main features:
 * - Automatic database connection management
 * - CRUD operations for sensor data with UUID-based identification
 * - Batch operations for multiple items
 * - Automatic timestamp management
 * - Data cleanup for old records
 * 
 * Communication is handled through postMessage with the following actions:
 * - store: Store single or multiple items
 * - getById: Retrieve a single item by ID
 * - getByIds: Retrieve multiple items by IDs
 * - getAll: Retrieve all stored items
 * - getAllIds: Retrieve all stored IDs
 * - update: Update an existing item
 * - delete: Delete a single item
 * - deleteMultiple: Delete multiple items
 * - cleanup: Remove old records
 * 
 * Database Schema:
 * - Store Name: figureStore
 * - Indices: timestamp, category, name
 * - Key Path: id (auto-generated UUID if not provided)
 * 
 * @example
 * // Usage from main thread:
 * const worker = new Worker('worker.js');
 * worker.postMessage({
 *   action: 'store',
 *   payload: { name: 'sensor1', data: [...] }
 * });
 * 
 * worker.onmessage = (e) => {
 *   if (e.data.status === 'success') {
 *     console.log('Operation successful:', e.data.result);
 *   }
 * };
 * 
 * @version 1.0
 * @license GPL-3.0
 */

// worker.js with ID-based storage and retrieval
let db = null;

/**
 * Opens and initializes the IndexedDB database connection
 * @returns {Promise<IDBDatabase>} A promise that resolves with the database instance
 */
function openDatabase() {
  return new Promise((resolve, reject) => {
    if (db) {
      resolve(db);
      return;
    }
    
    const request = indexedDB.open("SensorViewDB", 1);
    
    request.onupgradeneeded = function(event) {
      const db = event.target.result;
      if (!db.objectStoreNames.contains("figureStore")) {
        // Use auto-incrementing key if id is not provided
        const store = db.createObjectStore("figureStore", { 
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

/**
 * Stores data in the IndexedDB store
 * @param {Object|Array} data - Single item or array of items to store
 * @returns {Promise<Object>} Object containing status, count, and results of the operation
 */
async function storeData(data) {
  if (!db) await openDatabase();
  
  return new Promise((resolve, reject) => {
    const tx = db.transaction("figureStore", "readwrite");
    const store = tx.objectStore("figureStore");
    
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

/**
 * Retrieves a single item by its ID
 * @param {string|number} id - The ID of the item to retrieve
 * @returns {Promise<Object|undefined>} The retrieved item or undefined if not found
 */
async function getDataById(id) {
  if (!db) await openDatabase();
  
  return new Promise((resolve, reject) => {
    const tx = db.transaction("figureStore", "readonly");
    const store = tx.objectStore("figureStore");
    const request = store.get(id);
    
    request.onsuccess = () => resolve(request.result);
    request.onerror = (event) => reject(event.target.error);
  });
}

/**
 * Retrieves multiple items by their IDs
 * @param {Array<string|number>} ids - Array of IDs to retrieve
 * @returns {Promise<Array>} Array of retrieved items
 */
async function getDataByIds(ids) {
  if (!db) await openDatabase();
  
  return new Promise((resolve, reject) => {
    const tx = db.transaction("figureStore", "readonly");
    const store = tx.objectStore("figureStore");
    
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

/**
 * Retrieves all items from the store
 * @returns {Promise<Array>} Array of all items in the store
 */
async function getAllData() {
  if (!db) await openDatabase();
  
  return new Promise((resolve, reject) => {
    const tx = db.transaction("figureStore", "readonly");
    const store = tx.objectStore("figureStore");
    const request = store.getAll();
    
    request.onsuccess = () => resolve(request.result);
    request.onerror = (event) => reject(event.target.error);
  });
}

/**
 * Retrieves all IDs from the store
 * @returns {Promise<Array>} Array of all IDs in the store
 */
async function getAllIds() {
  if (!db) await openDatabase();
  
  return new Promise((resolve, reject) => {
    const tx = db.transaction("figureStore", "readonly");
    const store = tx.objectStore("figureStore");
    const request = store.getAllKeys();
    
    request.onsuccess = () => resolve(request.result);
    request.onerror = (event) => reject(event.target.error);
  });
}

/**
 * Updates specific fields of an item by its ID
 * @param {string|number} id - ID of the item to update
 * @param {Object} updates - Object containing the fields to update
 * @returns {Promise<Object>} Status object containing result of the update operation
 */
async function updateDataById(id, updates) {
  if (!db) await openDatabase();
  
  return new Promise((resolve, reject) => {
    const tx = db.transaction("figureStore", "readwrite");
    const store = tx.objectStore("figureStore");
    
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

/**
 * Deletes a single item by its ID
 * @param {string|number} id - ID of the item to delete
 * @returns {Promise<Object>} Status object containing result of the delete operation
 */
async function deleteDataById(id) {
  if (!db) await openDatabase();
  
  return new Promise((resolve, reject) => {
    const tx = db.transaction("figureStore", "readwrite");
    const store = tx.objectStore("figureStore");
    const request = store.delete(id);
    
    request.onsuccess = () => resolve({ 
      status: "complete", 
      message: `Item ${id} deleted`,
      id: id
    });
    request.onerror = (event) => reject(event.target.error);
  });
}

/**
 * Deletes multiple items by their IDs
 * @param {Array<string|number>} ids - Array of IDs to delete
 * @returns {Promise<Object>} Status object containing results of the delete operations
 */
async function deleteDataByIds(ids) {
  if (!db) await openDatabase();
  
  return new Promise((resolve, reject) => {
    const tx = db.transaction("figureStore", "readwrite");
    const store = tx.objectStore("figureStore");
    
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

/**
 * Removes records older than the specified age
 * @param {number} [maxAgeDays=2] - Maximum age in days for records to keep
 * @returns {Promise<Object>} Status object containing count of deleted records
 */
async function cleanupOldData(maxAgeDays = 2) {
  if (!db) await openDatabase();
  
  return new Promise((resolve, reject) => {
    const tx = db.transaction("figureStore", "readwrite");
    const store = tx.objectStore("figureStore");
    const index = store.index("timestamp");
    const cutoffTime = Date.now() - (maxAgeDays * 24 * 60 * 60 * 1000);
    
    const request = index.openCursor(IDBKeyRange.upperBound(cutoffTime));
    let deletedCount = 0;

    request.onsuccess = (event) => {
      const cursor = event.target.result;
      if (cursor) {
        store.delete(cursor.primaryKey);
        deletedCount++;
        cursor.continue();
      }
    };

    tx.oncomplete = () => {
      resolve({
        status: "complete",
        deletedCount: deletedCount,
        message: `Deleted ${deletedCount} old records`
      });
    };

    tx.onerror = (event) => reject(event.target.error);
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
      case "cleanup":
        result = await cleanupOldData(payload);
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