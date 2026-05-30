/** Trading API convenience service — re-exports from the central api module. */

import { api } from "@/lib/api";

export const tradingApi = {
  // Orders
  listOrders: api.listOrders,
  createOrder: api.createOrder,
  cancelOrder: api.cancelOrder,

  // Broker
  getBrokerStatus: api.getBrokerStatus,
  getBrokerAccount: api.getBrokerAccount,
  getBrokerPositions: api.getBrokerPositions,

  // Notify
  getNotifyConfig: api.getNotifyConfig,
  updateNotifyConfig: api.updateNotifyConfig,
  testNotify: api.testNotify,

  // Optimize
  startOptimize: api.startOptimize,
  optimizeStreamUrl: api.optimizeStreamUrl,
  getOptimizeResult: api.getOptimizeResult,

  // WS Feed
  getWSFeedStatus: api.getWSFeedStatus,
  subscribeWSFeed: api.subscribeWSFeed,

  // Indices
  getIndices: api.getIndices,
  saveIndicesConfig: api.saveIndicesConfig,

  // News
  getNews: api.getNews,

  // Minute line
  getMinuteLine: api.getMinuteLine,
};
