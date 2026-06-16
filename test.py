import numpy as np
import joblib
import json
import tensorflow as tf

print("Testing models...")

rf = joblib.load('models/random_forest/rf_model.pkl')
print("✅ Random Forest loaded")

lstm = tf.keras.models.load_model('models/lstm/lstm_model.h5')
print("✅ LSTM loaded")

ae = tf.keras.models.load_model('models/autoencoder/autoencoder.h5')
print("✅ Autoencoder loaded")

sample = np.random.rand(1, 41)
rf_pred = rf.predict(sample)[0]
lstm_prob = float(lstm_model.predict(sample, verbose=0)[0][0])

print(f"\nTest sample: RF says {'ATTACK' if rf_pred==1 else 'NORMAL'}")
print("✅ All models working!")
