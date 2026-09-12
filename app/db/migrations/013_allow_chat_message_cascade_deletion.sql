-- Migration 013: retain immutable transcripts while allowing parent FK cleanup.
-- A direct message UPDATE or DELETE invokes this trigger at depth 1. PostgreSQL
-- invokes it at a greater depth when an ON DELETE CASCADE from chat_sessions
-- removes its dependent messages.
CREATE OR REPLACE FUNCTION systemdb.prevent_chat_message_mutation() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'DELETE' AND pg_trigger_depth() > 1 THEN
        RETURN OLD;
    END IF;

    RAISE EXCEPTION 'chat_messages are immutable';
END;
$$ LANGUAGE plpgsql;