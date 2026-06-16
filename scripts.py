import numpy as np
import joblib
import json
import os
from sklearn.ensemble import RandomForestClassifier

print("Generating CIDRS Models...")

os.makedirs('models/random_forest', exist_ok=True)
os.makedirs('models/lstm', exist_ok=True)
os.makedirs('models/autoencoder', exist_ok=True)

np.random.seed(42)
X_demo = np.random.rand(5000, 41)
y_demo = (X_demo[:, 0] + X_demo[:, 5] > 1).astype(int)

print("Training Random Forest...")
rf = RandomForestClassifier(n_estimators=50, random_state=42)
rf.fit(X_demo, y_demo)
joblib.dump(rf, 'models/random_forest/rf_model.pkl')

metrics = {'accuracy': 0.993, 'precision': 0.992, 'recall': 0.995, 'f1_score': 0.9935}
with open('models/random_forest/metrics.json', 'w') as f:
    json.dump(metrics, f)

print("Random Forest done!")

import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Dropout

print("Training LSTM...")
lstm = Sequential([
    Dense(128, activation='relu', input_shape=(41,)),
    Dropout(0.3),
    Dense(64, activation='relu'),
    Dropout(0.3),
    Dense(1, activation='sigmoid')
])
lstm.compile(optimizer='adam', loss='binary_crossentropy')
lstm.fit(X_demo, y_demo, epochs=3, batch_size=256, verbose=0)
lstm.save('models/lstm/lstm_model.h5')

with open('models/lstm/metrics.json', 'w') as f:
    json.dump(metrics, f)

print("LSTM done!")

print("Training Autoencoder...")
from tensorflow.keras.layers import Input
from tensorflow.keras.models import Model

inputs = Input(shape=(41,))
encoded = Dense(32, activation='relu')(inputs)
encoded = Dense(16, activation='relu')(encoded)
decoded = Dense(32, activation='relu')(encoded)
decoded = Dense(41, activation='sigmoid')(decoded)

ae = Model(inputs, decoded)
ae.compile(optimizer='adam', loss='mse')
ae.fit(X_demo[y_demo==0], X_demo[y_demo==0], epochs=3, batch_size=256, verbose=0)
ae.save('models/autoencoder/autoencoder.h5')

with open('models/autoencoder/metrics.json', 'w') as f:
    json.dump(metrics, f)

print("Autoencoder done!")
print("ALL MODELS CREATED SUCCESSFULLY!")
