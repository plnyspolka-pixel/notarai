// AWS adapter for relay.mjs: DynamoDB keeps connection identifiers only (with a TTL);
// frames go straight from one connection to the other and are never written anywhere.
import { ApiGatewayManagementApiClient, PostToConnectionCommand } from "@aws-sdk/client-apigatewaymanagementapi";
import { DeleteItemCommand, DynamoDBClient, GetItemCommand, PutItemCommand } from "@aws-sdk/client-dynamodb";
import { createRelay } from "./relay.mjs";

const table = process.env.TABLE;
const db = new DynamoDBClient({});
const ttl = () => ({ N: String(Math.floor(Date.now() / 1000) + 3 * 3600) });   // API Gateway closes sockets after 2 h

const store = {
  async putWorker(office, id) {
    await db.send(new PutItemCommand({ TableName: table, Item: { pk: { S: "o#" + office }, conn: { S: id }, ttl: ttl() } }));
    await db.send(new PutItemCommand({ TableName: table, Item: { pk: { S: "c#" + id }, worker: { S: office }, ttl: ttl() } }));
  },
  async getWorker(office) {
    const found = await db.send(new GetItemCommand({ TableName: table, Key: { pk: { S: "o#" + office } }, ConsistentRead: true }));
    return found.Item?.conn?.S ?? null;
  },
  async putClient(id, office) {
    await db.send(new PutItemCommand({ TableName: table, Item: { pk: { S: "c#" + id }, office: { S: office }, ttl: ttl() } }));
  },
  async getClient(id) {
    const found = await db.send(new GetItemCommand({ TableName: table, Key: { pk: { S: "c#" + id } }, ConsistentRead: true }));
    return found.Item?.office ? { office: found.Item.office.S } : null;
  },
  async remove(id) {
    const found = await db.send(new GetItemCommand({ TableName: table, Key: { pk: { S: "c#" + id } }, ConsistentRead: true }));
    await db.send(new DeleteItemCommand({ TableName: table, Key: { pk: { S: "c#" + id } } }));
    const office = found.Item?.worker?.S;
    if (office) {
      // Only if this connection is still the registered one: a reconnect may have replaced it.
      await db.send(new DeleteItemCommand({
        TableName: table, Key: { pk: { S: "o#" + office } },
        ConditionExpression: "conn = :c", ExpressionAttributeValues: { ":c": { S: id } },
      })).catch(() => {});
    }
  },
};

export async function handler(event) {
  const { connectionId, routeKey, domainName, stage } = event.requestContext;
  const api = new ApiGatewayManagementApiClient({ endpoint: `https://${domainName}/${stage}` });
  const post = async (id, text) => {
    try {
      await api.send(new PostToConnectionCommand({ ConnectionId: id, Data: text }));
      return true;
    } catch {
      return false;
    }
  };
  const relay = createRelay({ store, post });
  // Nothing about the frame is logged: not its size, not its direction.
  if (routeKey === "$connect") return { statusCode: await relay.connect(connectionId, event.queryStringParameters) };
  if (routeKey === "$disconnect") {
    await relay.disconnect(connectionId);
    return { statusCode: 200 };
  }
  return { statusCode: await relay.message(connectionId, event.body) };
}
